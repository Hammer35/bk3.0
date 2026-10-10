"""Coverage of researched niche phrases by the user's own pins (gap analysis on own data only).

Pins are read from the user's own connected account. Matching is plain word matching in code:
nothing from the pins is sent to the model. This is not competitor research: no other account is read.
"""
import re

from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount

from .models import ResearchSnapshot
from .research import fresh_snapshot

_WORD = re.compile(r"[a-zа-я0-9]+")
_STOP = {"for", "and", "the", "with", "of", "in", "to", "on", "at", "from", "your", "you", "near", "me",
         "для", "и", "в", "на", "с", "по", "из", "от", "как", "что", "или", "при", "до"}
_INTENT = re.compile(
    r"(какие|что|где)\s+(?:\S+\s+){0,3}(запрос\w*|ключ\w*|фраз\w*|темы?)\s+(?:\S+\s+){0,5}(не\s+покрыт\w*|нет\s+(?:у\s+меня\s+)?(?:контента|пинов))|"
    r"\bпробел\w*\s+(?:в\s+)?(?:моём\s+|моем\s+|нашем\s+)?(?:контент\w*|ключ\w*|запрос\w*)|"
    r"не\s+покрыт\w*\s+(?:запрос\w*|ключ\w*|фраз\w*)|покрыти\w*\s+(?:запрос\w*|ключ\w*|ниш\w*)|\bgap[\s-]*analysis\b",
    re.I)
MAX_SHOWN = 12


def asks_for_coverage(message: str) -> bool:
    return bool(_INTENT.search(message))


def _stems(text: str) -> set[str]:
    """First five letters of every meaningful word; cheap, language-agnostic, plural-tolerant."""
    words = _WORD.findall((text or "").lower().replace("ё", "е"))
    return {w[:5] for w in words if len(w) > 2 and w not in _STOP}


def pin_text(pin: dict) -> str:
    return " ".join(str(pin.get(key) or "") for key in ("title", "description", "alt_text"))


def compute_coverage(candidates: list[dict], pins: list[dict]) -> list[dict]:
    """A phrase is covered by a pin when all its stems occur in the pin text (English or Russian form)."""
    pin_stems = [(_stems(pin_text(pin)), str(pin.get("title") or "")[:80]) for pin in pins if isinstance(pin, dict)]
    result = []
    for item in candidates:
        wanted = [s for s in (_stems(item["phrase"]), _stems(item.get("ru", ""))) if s]
        hits = [title for stems, title in pin_stems if any(w <= stems for w in wanted)]
        result.append({"phrase": item["phrase"], "ru": item.get("ru", ""), "pins": len(hits),
                       "covered": bool(hits), "example": next((t for t in hits if t), "")})
    return result


def _fetch_pins(business: Business, account: PinterestAccount):
    from .services import _read_all_pinterest_pages  # lazy: services imports this module
    return _read_all_pinterest_pages(business=business, account=account, resource="pins")


def build_coverage(business: Business, account: PinterestAccount, niche: ResearchSnapshot) -> tuple[ResearchSnapshot | None, str]:
    """Returns (snapshot, error). Reads the account's own pins, never anything of other accounts."""
    response = _fetch_pins(business, account)
    if response.get("error"):
        return None, f"Не удалось прочитать пины @{account.username}: {response['error']}"
    pins = response["items"]
    rows = compute_coverage(niche.candidates, pins)
    notices = [f"Основано на исследовании ниши от {niche.researched_at:%d.%m.%Y}.", f"Прочитано пинов: {len(pins)}."]
    if response.get("truncated"):
        notices.append("Пины прочитаны не полностью: достигнут предел чтения страниц, охват может быть занижен.")
    if not any(r["ru"] for r in rows):
        notices.append("Русских эквивалентов фраз нет: сравнение шло по английским словам и могло пропустить русский контент.")
    snapshot = ResearchSnapshot.objects.create(
        business=business, account=account, kind=ResearchSnapshot.Kind.COVERAGE, seeds=niche.seeds, region=niche.region,
        candidates=rows, notices=notices, researched_at=timezone.now())
    return snapshot, ""


def fresh_coverage(business: Business) -> ResearchSnapshot | None:
    return fresh_snapshot(business, kind=ResearchSnapshot.Kind.COVERAGE)


def render_coverage(snapshot: ResearchSnapshot, account: PinterestAccount) -> str:
    rows = snapshot.candidates
    uncovered = [r for r in rows if not r["covered"]]
    covered = sorted((r for r in rows if r["covered"]), key=lambda r: -r["pins"])

    def label(row):
        return row["phrase"] + (f" ({row['ru']})" if row["ru"] else "")

    lines = [f"Охват ниши вашими пинами, аккаунт @{account.username}. Фраз из исследования: {len(rows)}; без пинов: {len(uncovered)}."]
    if uncovered:
        lines += ["", "Пробелы (ни в одном пине нет этих слов):"] + [f"- {label(r)}" for r in uncovered[:MAX_SHOWN]]
        if len(uncovered) > MAX_SHOWN:
            lines.append(f"- … и ещё {len(uncovered) - MAX_SHOWN}")
    if covered:
        lines += ["", "Уже покрыты:"] + [f"- {label(r)}: пинов {r['pins']}" + (f", например «{r['example']}»" if r["example"] else "")
                                         for r in covered[:MAX_SHOWN]]
    lines += [""] + [f"Замечание: {n}" for n in snapshot.notices]
    lines += ["Совпадение определено по словам в названии, описании и тексте картинки пинов. Это не позиции в поиске, не спрос и не оценка качества пинов.",
              "Когда будешь готов, напиши «Построй стратегию»: пробелы учтутся."]
    return "\n".join(lines)


def coverage_reply(*, user_message, actor=None):
    """Chat entry; returns an AIMessage or None when the message is not a coverage request."""
    from .models import AIMessage
    from .services import _account_for_pinterest_request

    if not asks_for_coverage(user_message.content):
        return None
    conversation = user_message.conversation
    business = conversation.business

    def reply(text, model="coverage"):
        return AIMessage.objects.create(conversation=conversation, role=AIMessage.Role.ASSISTANT, content=text,
                                        provider="coverage", model=model)

    niche = fresh_snapshot(business)
    if niche is None:
        return reply("Для сравнения нужны фразы ниши. Сначала напиши «Исследуй нишу».", "coverage-needs-research")
    accounts = list(PinterestAccount.objects.filter(business=business, deleted_at__isnull=True).order_by("created_at"))
    connected = [a for a in accounts if a.status == PinterestAccount.Status.CONNECTED]
    if not connected:
        return reply("Для сравнения нужен подключённый аккаунт Pinterest этого бизнеса.", "coverage-needs-account")
    account = _account_for_pinterest_request(user_message.content, accounts)
    if account is None:
        names = ", ".join(f"@{a.username}" for a in connected)
        return reply(f"Укажи, чей контент сравнивать: {names}.", "coverage-needs-account")
    snapshot, error = build_coverage(business, account, niche)
    if error:
        return reply(error, "coverage-read-error")
    return reply(render_coverage(snapshot, account))
