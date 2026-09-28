from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from pathlib import Path
import re

import yaml


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")


@dataclass(frozen=True)
class KnowledgeSource:
    source_id: str
    title: str
    source_path: str
    language: str
    scope: str
    status: str
    source_checked: date | None
    effective_until: date | None
    source_links: list[str]
    metadata: dict
    content: str
    content_hash: str


def load_approved_sources(directory: Path, *, project_root: Path) -> list[KnowledgeSource]:
    sources = []
    for path in sorted(directory.glob("*.md")):
        source = load_source(path, project_root=project_root)
        if source.status == "approved" and source.scope == "global":
            sources.append(source)
    return sources


def load_source(path: Path, *, project_root: Path) -> KnowledgeSource:
    raw = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(raw)
    if not match:
        raise ValueError(f"Knowledge document has no valid YAML front matter: {path}")

    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Knowledge document metadata must be a mapping: {path}")
    content = match.group(2).strip()
    source_id = metadata.get("id")
    if not source_id:
        raise ValueError(f"Knowledge document is missing id: {path}")

    title_match = TITLE_RE.search(content)
    title = title_match.group(1).strip() if title_match else source_id
    source_checked = _as_date(metadata.get("source_checked"))
    effective_until = _as_date(metadata.get("rules_effective_until"))
    return KnowledgeSource(
        source_id=str(source_id),
        title=title,
        source_path=path.relative_to(project_root).as_posix(),
        language=str(metadata.get("language", "ru")),
        scope=str(metadata.get("scope", "global")),
        status=str(metadata.get("status", "candidate")),
        source_checked=source_checked,
        effective_until=effective_until,
        source_links=list(dict.fromkeys(LINK_RE.findall(content))),
        metadata=metadata,
        content=content,
        content_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    return date.fromisoformat(str(value))
