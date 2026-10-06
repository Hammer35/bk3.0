"""Prompt versions and context manifests: which prompt and which sources produced a reply.

A manifest lists what was put in front of the model (kinds and identifiers, never the text
of the data). Prompt versions are bumped by hand; FINGERPRINTS pins each version to the hash of
its template, and a test fails when a prompt changes without a new version.
"""
import hashlib
from types import SimpleNamespace

from django.utils.translation import gettext as _

CHAT_PROMPT_VERSION = "chat-2026-10-06.2"
STRATEGY_PROMPT_VERSION = "strategy-2026-10-06.1"
PLAN_PROMPT_VERSION = "content-plan-2026-10-06.2"
RESEARCH_PROMPT_VERSION = "research-2026-10-06.1"
PIN_PROMPT_VERSION = "pin-2026-10-06.3"

FINGERPRINTS = {
    "chat-2026-10-06.2": "217b14366345",
    "strategy-2026-10-06.1": "5cfb5ea333b3",
    "content-plan-2026-10-06.2": "8cd5c05c0a5d",
    "research-2026-10-06.1": "be53792a2b51",
    "pin-2026-10-06.3": "593fcf5ba02e",
}


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def stamp(version: str, text: str = "") -> str:
    """Stored on the message: the template version, plus a hash of the exact assembled prompt if given."""
    return f"{version}#{fingerprint(text)}" if text else version


def template_fingerprints() -> dict[str, str]:
    """Hashes of the current templates, with fixed dummy data for the chat prompt."""
    from . import content_plan, pin_generation, research, strategy_chat
    from .prompts import build_strategist_system_prompt

    business = SimpleNamespace(name="B", website="https://example.com", niche="N", subniche="S", market="M",
                               audience="A", goals="G")
    chat = build_strategist_system_prompt(
        business, knowledge_context="K",
        pinterest_accounts=[{"username": "u", "account_key": "k", "status": "s", "scopes": ["x"]}],
        memory_facts=["f"])
    return {
        CHAT_PROMPT_VERSION: fingerprint(chat),
        STRATEGY_PROMPT_VERSION: fingerprint(strategy_chat.SYSTEM),
        PLAN_PROMPT_VERSION: fingerprint(content_plan.SYSTEM + content_plan.RETRY_NOTE),
        RESEARCH_PROMPT_VERSION: fingerprint(research.SEED_SYSTEM + research.FILTER_SYSTEM),
        PIN_PROMPT_VERSION: fingerprint(pin_generation.SYSTEM),
    }


def describe(manifest) -> list[str]:
    """Human lines for the manifest of one reply (translated, no stored data text)."""
    from .strategy import FIELD_LABELS

    lines = []
    for entry in manifest if isinstance(manifest, list) else []:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("type")
        if kind == "business_profile":
            fields = ", ".join(_(FIELD_LABELS.get(f, f)) for f in entry.get("fields", []))
            lines.append(_("Профиль бизнеса: %(fields)s") % {"fields": fields})
        elif kind == "business_memory" and entry.get("ids"):
            lines.append(_("Память бизнеса: фактов %(count)s") % {"count": len(entry["ids"])})
        elif kind == "history":
            lines.append(_("История диалога: сообщений %(count)s") % {"count": entry.get("messages", 0)})
        elif kind == "knowledge" and entry.get("documents"):
            titles = "; ".join(str(d.get("title") or d.get("source_id") or "") for d in entry["documents"][:5])
            lines.append(_("База знаний: %(titles)s") % {"titles": titles})
        elif kind == "pinterest_read":
            resources = ", ".join(sorted({str(c.get("resource")) for c in entry.get("calls", [])}))
            lines.append(_("Данные Pinterest через API: %(resources)s") % {"resources": resources})
        elif kind == "wb":
            lines.append(_("Данные Wildberries: %(what)s") % {"what": entry.get("what", "")})
        elif kind == "research_snapshot":
            lines.append(_("Исследование ниши от %(date)s") % {"date": entry.get("date", "")})
        elif kind == "strategy_version":
            lines.append(_("Подтверждённая стратегия, версия %(number)s") % {"number": entry.get("number", "")})
        elif kind == "sources" and entry.get("refs"):
            lines.append(_("Источники черновика: %(count)s") % {"count": len(entry["refs"])})
    return lines
