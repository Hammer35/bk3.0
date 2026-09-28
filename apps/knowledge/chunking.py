from dataclasses import dataclass
import re


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
NON_KNOWLEDGE_HEADINGS = {"источники", "источник", "ссылки", "источники и ссылки", "references"}


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    heading: str
    content: str


def chunk_markdown(text: str, *, max_chars: int = 2800, overlap_chars: int = 350) -> list[TextChunk]:
    """Split markdown at headings and paragraph/sentence boundaries with local overlap."""
    if max_chars < 256:
        raise ValueError("max_chars must be at least 256")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

    sections = _sections(text)
    chunks: list[TextChunk] = []

    for heading, body in sections:
        if heading.casefold() in NON_KNOWLEDGE_HEADINGS:
            continue
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
        current = ""

        for paragraph in paragraphs:
            units = _split_long_paragraph(paragraph, max_chars)
            for unit in units:
                candidate = "\n\n".join(part for part in (current, unit) if part)
                if len(candidate) <= max_chars:
                    current = candidate
                    continue

                if current:
                    chunks.append(TextChunk(len(chunks), heading, _with_heading(heading, current)))
                    current = _overlap_tail(current, overlap_chars)

                candidate = "\n\n".join(part for part in (current, unit) if part)
                if len(candidate) > max_chars:
                    # A heading may be unusually long; keep the body bounded regardless.
                    current = unit[-max_chars:]
                else:
                    current = candidate

        if current:
            chunks.append(TextChunk(len(chunks), heading, _with_heading(heading, current)))

    return chunks


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [("", text.strip())] if text.strip() else []

    sections: list[tuple[str, str]] = []
    preamble = text[:matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = match.group(2).strip()
        body = text[match.end():end].strip()
        sections.append((heading, body))
    return sections


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]

    sentences = SENTENCE_RE.split(paragraph)
    units: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                units.append(current)
                current = ""
            for start in range(0, len(sentence), max_chars):
                units.append(sentence[start:start + max_chars])
            continue
        candidate = " ".join(part for part in (current, sentence) if part)
        if len(candidate) > max_chars:
            units.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        units.append(current)
    return units


def _overlap_tail(text: str, overlap_chars: int) -> str:
    if not overlap_chars:
        return ""
    tail = text[-overlap_chars:]
    first_space = tail.find(" ")
    return tail[first_space + 1:] if first_space >= 0 else tail


def _with_heading(heading: str, content: str) -> str:
    return f"{heading}\n\n{content}" if heading else content
