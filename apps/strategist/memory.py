"""Business memory: facts the user explicitly asked to remember, and decisions with reasons."""
import re

from apps.workspaces.models import Membership

from .models import AIMessage, BusinessMemory

EDIT_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.EDITOR}
MAX_FACTS = 50
MAX_DECISIONS = 200
TEXT_LIMIT = 300
_REMEMBER = re.compile(r"^\s*(?:запомни|запиши|зафиксируй)\s*[:,\-—]?\s+(.+)$", re.I | re.S)
_FORGET = re.compile(r"^\s*(?:забудь|удали\s+из\s+памяти)\s*[:,\-—]?\s+(.+)$", re.I | re.S)
_SHOW = re.compile(r"что\s+ты\s+(?:помнишь|знаешь\s+о\s+(?:моём|моем)\s+бизнесе)|покажи\s+(?:мою\s+)?память|что\s+в\s+памяти", re.I)
_SENSITIVE = re.compile(
    r"пароль|password|токен|token|api[\s_-]?key|секретн|secret|cvv|cvc|логин|паспорт|снилс|\bинн\b"
    r"|[\w.+-]+@[\w-]+\.[\w.]+|\d[\d\s-]{10,}\d", re.I)


def actor_can_edit(business, actor) -> bool:
    return bool(actor) and Membership.objects.filter(
        workspace=business.workspace, user=actor, role__in=EDIT_ROLES).exists()


def facts(business) -> list[BusinessMemory]:
    return list(business.memory_items.filter(kind=BusinessMemory.Kind.FACT).order_by("created_at", "id"))


def memory_ref(item: BusinessMemory) -> str:
    return f"memory:{item.pk}"


def prompt_lines(business) -> list[str]:
    return [item.text for item in facts(business)]


def record_decision(business, user, text: str, *, reason: str = "", source_ref: str) -> BusinessMemory:
    item = BusinessMemory.objects.create(
        business=business, kind=BusinessMemory.Kind.DECISION, text=" ".join(text.split())[:TEXT_LIMIT],
        reason=" ".join(reason.split())[:TEXT_LIMIT], source_ref=source_ref[:80], created_by=user)
    stale = business.memory_items.filter(kind=BusinessMemory.Kind.DECISION).order_by("-created_at", "-id")[MAX_DECISIONS:]
    BusinessMemory.objects.filter(pk__in=[s.pk for s in stale]).delete()
    return item


def _remember(business, user, text: str, source_ref: str) -> str:
    text = " ".join(text.split()).strip(" .")
    if not text:
        return "Что именно запомнить? Напиши факт после слова «Запомни»."
    if _SENSITIVE.search(text):
        return "Такое я не запоминаю: не храню пароли, ключи, платёжные и личные данные."
    if len(text) > TEXT_LIMIT:
        return f"Слишком длинно: в памяти хранится до {TEXT_LIMIT} символов на факт. Сократи или раздели."
    current = facts(business)
    if any(f.text.casefold() == text.casefold() for f in current):
        return "Это я уже помню."
    if len(current) >= MAX_FACTS:
        return f"В памяти уже {MAX_FACTS} фактов. Скажи «Забудь: …», чтобы освободить место."
    BusinessMemory.objects.create(business=business, kind=BusinessMemory.Kind.FACT, text=text,
                                  source_ref=source_ref, created_by=user)
    return f"Запомнил: {text}. Это факт, который ты сообщил; я не проверял его по внешним источникам."


def _forget(business, term: str) -> str:
    term = " ".join(term.split()).strip(" .")
    if len(term) < 3:
        return "Уточни, что забыть: нужно хотя бы три символа."
    matches = [f for f in facts(business) if term.casefold() in f.text.casefold()]
    if not matches:
        return "Не нашёл такого среди сохранённых фактов. Спроси «Что ты помнишь?»."
    BusinessMemory.objects.filter(pk__in=[m.pk for m in matches]).delete()
    return "Забыл:\n" + "\n".join(f"- {m.text}" for m in matches)


def _show(business) -> str:
    items = facts(business)
    decisions = list(business.memory_items.filter(kind=BusinessMemory.Kind.DECISION)[:10])
    if not items and not decisions:
        return "Пока ничего не помню. Скажи «Запомни: …», и я сохраню факт о бизнесе."
    lines = []
    if items:
        lines += ["Факты, которые ты просил запомнить:"] + [f"- {i.text}" for i in items]
    if decisions:
        lines += ([""] if lines else []) + ["Последние решения:"]
        lines += [f"- {d.text}" + (f" (причина: {d.reason})" if d.reason else "") + f" — {d.created_at:%d.%m.%Y}" for d in decisions]
    return "\n".join(lines)


def memory_reply(*, user_message: AIMessage, actor=None) -> AIMessage | None:
    """Handle remember/forget/show commands; None when the message is not one."""
    text = user_message.content
    remember, forget, show = _REMEMBER.match(text), _FORGET.match(text), _SHOW.search(text)
    if not (remember or forget or show):
        return None
    conversation = user_message.conversation
    business = conversation.business
    if (remember or forget) and not actor_can_edit(business, actor):
        answer = "Менять память бизнеса могут владелец, администратор и редактор рабочего пространства."
    elif remember:
        answer = _remember(business, actor, remember.group(1), f"user_message:{user_message.pk}")
    elif forget:
        answer = _forget(business, forget.group(1))
    else:
        answer = _show(business)
    return AIMessage.objects.create(conversation=conversation, role=AIMessage.Role.ASSISTANT,
                                    content=answer, provider="memory", model="business-memory")
