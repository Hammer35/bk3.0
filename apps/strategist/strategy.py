"""Strategy drafts: bounded validation, immutable versions and explicit confirmation.

The model may only propose content; this module decides what is stored. Every
rationale item must cite a source that really exists in the manifest, numbers
about cadence are never accepted as facts unless the user stated them, and
exclusions the user asked for are enforced here, not left to the prompt.
"""
import re

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.businesses.models import Business
from . import memory
from .models import Strategy, StrategyVersion

PROFILE_FIELDS = ("name", "website", "niche", "subniche", "market", "audience", "goals")
REQUIRED_PROFILE_FIELDS = ("niche", "audience", "goals")
FIELD_LABELS = {
    "name": "название", "website": "сайт", "niche": "ниша", "subniche": "подниша",
    "market": "рынок", "audience": "целевая аудитория", "goals": "цели бизнеса",
}
LIST_SECTIONS = {
    "goals": 5, "priorities": 7, "content_directions": 10, "seasonal_plans": 8,
    "hypotheses": 10, "missing_data": 10, "recommended_boards": 10, "keyword_clusters": 10,
}
TEXT_LIMIT = 300
DEMAND_WORDS = r"спрос|интерес|популярн|тренд|растёт|растет|рост[а-я]*\s+(?:запрос|поиск)|ищут|востребован"
KEYWORDS_PER_CLUSTER = 15


class StrategyError(Exception):
    """Safe-to-show reason a strategy operation was refused."""


def profile_facts(business: Business) -> dict[str, str]:
    """Non-empty profile fields keyed by the reference used in rationale items."""
    facts = {}
    for field in PROFILE_FIELDS:
        value = (getattr(business, field) or "").strip()
        if value:
            facts[f"profile:{field}"] = value
    return facts


def missing_profile_fields(business: Business) -> list[str]:
    return [FIELD_LABELS[f] for f in REQUIRED_PROFILE_FIELDS if not (getattr(business, f) or "").strip()]


def research_ref(snapshot) -> str:
    return f"research:{snapshot.public_id}"


def build_sources(facts: dict[str, str], *, user_message_ids=(), snapshots=(), memory_items=()) -> list[dict]:
    sources = [{"ref": ref, "type": "business_profile", "value": value[:TEXT_LIMIT]} for ref, value in facts.items()]
    sources += [{"ref": f"user_message:{pk}", "type": "user_message"} for pk in user_message_ids]
    sources += [{"ref": f"memory:{m.pk}", "type": "business_memory", "value": m.text[:TEXT_LIMIT]} for m in memory_items]
    sources += [{"ref": research_ref(s), "type": "research_snapshot", "researched_at": s.researched_at.isoformat()}
                for s in snapshots]
    return sources


def _text(value) -> str:
    return " ".join(value.split())[:TEXT_LIMIT] if isinstance(value, str) else ""


def _text_items(value, limit: int) -> list[str]:
    items = value if isinstance(value, list) else []
    return [t for t in (_text(i) for i in items) if t][:limit]


def _clusters(value) -> list[dict]:
    result = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        keywords = _text_items(item.get("keywords"), KEYWORDS_PER_CLUSTER)
        if name and keywords:
            result.append({"name": name, "keywords": keywords})
    return result[: LIST_SECTIONS["keyword_clusters"]]


def _boards(value) -> list[dict]:
    result = []
    for item in value if isinstance(value, list) else []:
        name = _text(item.get("name") if isinstance(item, dict) else item)
        if name:
            purpose = _text(item.get("purpose")) if isinstance(item, dict) else ""
            result.append({"name": name, "purpose": purpose})
    return result[: LIST_SECTIONS["recommended_boards"]]


def _seasons(value) -> list[dict]:
    result = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and _text(item.get("period")) and _text(item.get("idea")):
            result.append({"period": _text(item["period"]), "idea": _text(item["idea"])})
    return result[: LIST_SECTIONS["seasonal_plans"]]


def clean_payload(raw, *, allowed_refs, exclusions=(), user_stated_cadence: str = "", allowed_keywords=None) -> dict:
    """Return a storable payload or raise StrategyError; never trust model output.

    allowed_keywords: phrases actually found by research. When given, keyword
    clusters keep only those phrases; None disables the filter (tests/legacy).
    """
    if not isinstance(raw, dict):
        raise StrategyError("Не удалось разобрать черновик стратегии.")
    allowed = set(allowed_refs)
    hypotheses = _text_items(raw.get("hypotheses"), LIST_SECTIONS["hypotheses"])
    rationale = []
    for item in raw.get("rationale") if isinstance(raw.get("rationale"), list) else []:
        if not isinstance(item, dict):
            continue
        claim = _text(item.get("claim"))
        refs = [r for r in (item.get("basis") if isinstance(item.get("basis"), list) else [])
                if isinstance(r, str) and r in allowed]
        if not claim:
            continue
        demand_claim = re.search(DEMAND_WORDS, claim, re.I)
        if refs and demand_claim and all(r.startswith("research:") for r in refs):
            hypotheses.append(claim)  # a found phrase does not prove audience interest or demand
        elif refs:
            rationale.append({"claim": claim, "basis": sorted(set(refs))})
        else:  # no real source: it is a hypothesis, not an established reason
            hypotheses.append(claim)
    cadence_text = _text((raw.get("publishing_cadence") or {}).get("text")) if isinstance(raw.get("publishing_cadence"), dict) else ""
    cadence = {}
    if cadence_text:
        stated = bool(user_stated_cadence) and cadence_text.lower() == user_stated_cadence.lower()
        cadence = {"text": cadence_text, "basis": "user" if stated else "hypothesis"}
    payload = {
        "goals": _text_items(raw.get("goals"), LIST_SECTIONS["goals"]),
        "priorities": _text_items(raw.get("priorities"), LIST_SECTIONS["priorities"]),
        "keyword_clusters": _clusters(raw.get("keyword_clusters")),
        "recommended_boards": _boards(raw.get("recommended_boards")),
        "content_directions": _text_items(raw.get("content_directions"), LIST_SECTIONS["content_directions"]),
        "publishing_cadence": cadence,
        "seasonal_plans": _seasons(raw.get("seasonal_plans")),
        "rationale": rationale,
        "hypotheses": list(dict.fromkeys(hypotheses))[: LIST_SECTIONS["hypotheses"]],
        "missing_data": _text_items(raw.get("missing_data"), LIST_SECTIONS["missing_data"]),
        "exclusions": [e for e in (_text(x) for x in exclusions) if e],
    }
    if allowed_keywords is not None:
        known = {k.casefold() for k in allowed_keywords}
        clusters = [{"name": c["name"], "keywords": [k for k in c["keywords"] if k.casefold() in known]}
                    for c in payload["keyword_clusters"]]
        payload["keyword_clusters"] = [c for c in clusters if c["keywords"]]
        if not payload["keyword_clusters"]:
            note = "Ключевые слова не подтверждены исследованием: напиши «Исследуй нишу»."
            payload["missing_data"] = [m for m in payload["missing_data"] if m != note][:LIST_SECTIONS["missing_data"] - 1] + [note]
    payload = apply_exclusions(payload, payload["exclusions"])
    if not payload["goals"] and not payload["content_directions"]:
        raise StrategyError("В черновике нет целей и контентных направлений.")
    return payload


def _mentions(value, terms) -> bool:
    if isinstance(value, dict):
        value = " ".join(str(v) for v in value.values())
    elif isinstance(value, list):
        value = " ".join(str(v) for v in value)
    text = str(value).casefold()
    return any(t.casefold() in text for t in terms)


def apply_exclusions(payload: dict, exclusions) -> dict:
    """Drop every proposed item that mentions something the user ruled out."""
    terms = [e for e in exclusions if e]
    if not terms:
        return payload
    cleaned = dict(payload)
    for section in ("goals", "priorities", "keyword_clusters", "recommended_boards",
                    "content_directions", "seasonal_plans", "hypotheses"):
        cleaned[section] = [i for i in payload[section] if not _mentions(i, terms)]
    cleaned["rationale"] = [i for i in payload["rationale"] if not _mentions(i["claim"], terms)]
    if payload["publishing_cadence"] and _mentions(payload["publishing_cadence"], terms):
        cleaned["publishing_cadence"] = {}
    return cleaned


@transaction.atomic
def create_draft(business: Business, user, payload: dict, *, sources: list[dict], change_note: str = "", snapshots=()) -> StrategyVersion:
    strategy = (Strategy.objects.select_for_update()
                .filter(business=business).exclude(status=Strategy.Status.ARCHIVED)
                .order_by("-created_at").first())
    if strategy is None:
        strategy = Strategy.objects.create(business=business)
    number = (strategy.versions.aggregate(m=Max("number"))["m"] or 0) + 1
    strategy.versions.filter(status=StrategyVersion.Status.DRAFT).update(status=StrategyVersion.Status.SUPERSEDED)
    version = StrategyVersion.objects.create(
        strategy=strategy, number=number, created_by=user, sources=sources,
        change_note=_text(change_note)[:500], **payload,
    )
    version.research_snapshots.set(snapshots)
    return version


@transaction.atomic
def confirm_version(version: StrategyVersion, user) -> StrategyVersion:
    strategy = Strategy.objects.select_for_update().get(pk=version.strategy_id)
    version = StrategyVersion.objects.select_for_update().get(pk=version.pk)
    if version.status != StrategyVersion.Status.DRAFT:
        raise StrategyError("Подтвердить можно только актуальный черновик.")
    strategy.versions.filter(status=StrategyVersion.Status.CONFIRMED).update(status=StrategyVersion.Status.SUPERSEDED)
    version.status = StrategyVersion.Status.CONFIRMED
    version.confirmed_by = user
    version.confirmed_at = timezone.now()
    version.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
    strategy.active_version = version
    strategy.status = Strategy.Status.ACTIVE
    strategy.save(update_fields=["active_version", "status", "updated_at"])
    return version


def pending_draft(business: Business) -> StrategyVersion | None:
    return (StrategyVersion.objects
            .filter(strategy__business=business, status=StrategyVersion.Status.DRAFT)
            .exclude(strategy__status=Strategy.Status.ARCHIVED).order_by("-number").first())


def active_version(business: Business) -> StrategyVersion | None:
    strategy = (Strategy.objects.filter(business=business, status=Strategy.Status.ACTIVE)
                .select_related("active_version").order_by("-created_at").first())
    return strategy.active_version if strategy else None


def ref_label(ref: str) -> str:
    """Human label for a source reference shown next to a rationale item."""
    if ref.startswith("profile:"):
        return "профиль: " + FIELD_LABELS.get(ref.split(":", 1)[1], ref)
    if ref.startswith("memory:"):
        return "память бизнеса"
    if ref.startswith("research:"):
        return "исследование ниши"
    return "ваше сообщение" if ref.startswith("user_message:") else ref


def confirm_with_decision(version: StrategyVersion, user) -> StrategyVersion:
    """Confirm a draft and record the decision with its reason and author."""
    version = confirm_version(version, user)
    memory.record_decision(version.strategy.business, user, f"Подтверждена стратегия, версия {version.number}",
                           reason=version.change_note, source_ref=f"strategy_version:{version.pk}")
    return version
