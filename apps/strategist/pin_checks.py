"""Heavy validation of one pin version: deterministic checks with pass / review / block / not_checked.

Rules come from docs/ai-knowledge/knowledge/pinterest-spam-prevention.md and docs/PIN_QUALITY_CRITERIA.md.
A check that cannot be performed with the data we have is reported as `not_checked`, never as a pass.
`PASS` only means our checks passed; it is not an approval by Pinterest or by the user, and it does not
predict reach. Nothing here calls a model or a network.
"""
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .coverage import _stems

PASS, REVIEW, BLOCK, NOT_CHECKED = "pass", "review", "block", "not_checked"
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "clck.ru", "vk.cc", "ow.ly", "rebrand.ly", "pin.it"}
DUPLICATE_BLOCK = 0.85
DUPLICATE_REVIEW = 0.6
STUFFING_FRAGMENTS = 6
STUFFING_REPEATS = 4
_WORD = re.compile(r"[a-zа-я0-9]+")
_STOP = {"for", "and", "the", "with", "of", "in", "to", "on", "для", "и", "в", "на", "с", "по", "из", "от", "как", "что", "или"}
_BLOCK_CLAIM = re.compile(r"гарант\w*|100\s*%|сто\s+процентов|без\s+риска|№\s*1\b|number\s*one|#\s*1\b", re.I)
_REVIEW_CLAIM = re.compile(
    r"\bлучш\w*|единственн\w*|\bсамы[йе]\s+\w+|\bсамая\s+\w+|\bсамое\s+\w+|идеальн\w*|бесплатн\w*"
    r"|только\s+сегодня|успей\w*|\d+\s*%", re.I)
# Offers and social proof the model cannot know: blocked unless the linked product card mentions them.
_UNSOURCED = re.compile(r"скидк\w*|акци[яиюй]\b|распродаж\w*|эксклюзив\w*|(?:реальн|настоящ|честн)\w*\s+отзыв\w*|отзыв\w*\s+покупател\w*|"
                        r"бестселлер\w*|хит\s+продаж", re.I)
# Empty advertising phrases: they say nothing about the pin and read as machine text.
_CLICHE = re.compile(
    r"откро\w+\s+(?:для\s+себя|мир)|вдохни\w*\s+(?:жизнь|новую|в\s+)|погруз\w+(?:сь|итесь)|ждут\s+вас|прямо\s+сейчас|не\s+упусти\w*|"
    r"секрет\w*\s+успеха|ваш\s+идеальн\w*|уникальн\w*|стильн\w+\s+(?:и|,)\s+\w+|трендов\w+\s+находк\w*|"
    r"лучш\w+\s+из\s+лучших|раскро\w+\s+секрет|незаменим\w*|на\s+любой\s+вкус|в\s+любой\s+ситуации|"
    r"подчерк\w+\s+(?:ваш\w*|свою|вашу)\s+(?:стиль|индивидуальность)|станут\s+\w+\s+спутник\w*", re.I)
_NUMBER_UNIT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:см|мм|кг|мл|шт|вт|гб|дн\w*|час\w*|мин\w*|₽|руб\w*|\bг\b|\bм\b|\bл\b)", re.I)


@dataclass
class CheckContext:
    """What the checks may compare against; every field is optional data that may simply be missing."""
    content_directions: list[str] = field(default_factory=list)
    boards: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    limits: dict = field(default_factory=dict)          # {"title": int, "description": int} from the approved spec source
    other_texts: list[str] = field(default_factory=list)  # title + description of the business's other pin versions
    product_facts: str = ""                              # text of the linked product card, if any
    keyword_ru: str = ""                                 # Russian equivalent of the pin's keyword from the research


def _result(check_id: str, status: str, message: str) -> dict:
    return {"id": check_id, "status": status, "message": message}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower().replace("ё", "е")) if len(w) > 2 and w not in _STOP}


def similarity(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def _title_problem(title: str) -> str:
    if ":" in title:
        return "В заголовке двоеточие: шаблон «Тема: подзаголовок» не принимается, сформулируйте заголовок одной фразой."
    if "|" in title or "#" in title:
        return "В заголовке служебные знаки («|», «#»): заголовок должен читаться как обычная фраза."
    if "!" in title:
        return "В заголовке восклицательный знак: заголовок должен быть спокойной конкретной фразой."
    letters = [c for c in title if c.isalpha()]
    if len(letters) > 8 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        return "Заголовок написан заглавными буквами."
    return ""


def check_text_present(pin: dict) -> dict:
    if not (pin.get("title") or "").strip():
        return _result("text_present", BLOCK, "У пина нет заголовка.")
    problem = _title_problem(pin["title"])
    if problem:
        return _result("text_present", BLOCK, problem)
    cliche = _CLICHE.search(f"{pin['title']} {pin.get('description') or ''}")
    if cliche:
        return _result("text_present", BLOCK, f"Шаблонная рекламная фраза «{cliche.group(0).strip()}» ничего не сообщает о пине: опишите, что именно показано и чем это полезно.")
    if not (pin.get("description") or "").strip():
        return _result("text_present", REVIEW, "У пина нет описания: оно помогает определить релевантность.")
    return _result("text_present", PASS, "Заголовок и описание заданы.")


def check_text_limits(pin: dict, ctx: CheckContext) -> dict:
    if not ctx.limits:
        return _result("text_limits", NOT_CHECKED, "Актуальные лимиты длины текста недоступны (нет действующего источника).")
    over = []
    if len(pin.get("title") or "") > ctx.limits["title"]:
        over.append(f"заголовок {len(pin['title'])} из {ctx.limits['title']} символов")
    if len(pin.get("description") or "") > ctx.limits["description"]:
        over.append(f"описание {len(pin['description'])} из {ctx.limits['description']} символов")
    if over:
        return _result("text_limits", BLOCK, "Превышен технический лимит: " + "; ".join(over) + ".")
    return _result("text_limits", PASS, "Длина заголовка и описания в пределах технических лимитов справки Pinterest.")


def check_strategy_match(pin: dict, ctx: CheckContext) -> dict:
    text = f"{pin.get('title', '')} {pin.get('description', '')} {pin.get('alt_text', '')}".casefold()
    hit = next((e for e in ctx.exclusions if e and e.casefold() in text), None)
    if hit:
        return _result("strategy_match", BLOCK, f"Текст затрагивает исключённое пользователем: «{hit}».")
    if pin.get("direction") not in ctx.content_directions:
        return _result("strategy_match", BLOCK, "Направление пина отсутствует в подтверждённой стратегии.")
    if not pin.get("board"):
        return _result("strategy_match", REVIEW, "Доска не указана: нужно выбрать доску из стратегии.")
    if pin["board"] not in ctx.boards:
        return _result("strategy_match", REVIEW, "Доска пина не входит в рекомендованные стратегией.")
    return _result("strategy_match", PASS, "Направление и доска соответствуют подтверждённой стратегии.")


def check_keyword_use(pin: dict, ctx: CheckContext) -> dict:
    description = pin.get("description") or ""
    fragments = [f for f in re.split(r"[,;|/\n]", description) if f.strip()]
    counts = {}
    for word in _WORD.findall(description.lower()):
        if len(word) > 3 and word not in _STOP:
            counts[word] = counts.get(word, 0) + 1
    repeated = [w for w, n in counts.items() if n >= STUFFING_REPEATS]
    if len(fragments) >= STUFFING_FRAGMENTS and sum(len(f.split()) <= 3 for f in fragments) >= STUFFING_FRAGMENTS:
        return _result("keyword_use", BLOCK, "Описание похоже на список ключевых слов (набивка), а не на связный текст.")
    if repeated:
        return _result("keyword_use", BLOCK, f"Слово «{repeated[0]}» повторяется в описании слишком часто (набивка ключевыми словами).")
    keyword = pin.get("keyword") or ""
    if not keyword:
        return _result("keyword_use", REVIEW, "Ключевая фраза пина не задана.")
    if keyword not in ctx.keywords:
        return _result("keyword_use", BLOCK, "Ключевой фразы нет среди подтверждённых исследованием фраз стратегии.")
    wanted = [w for w in (_stems(keyword), _stems(ctx.keyword_ru)) if w]
    stems = _stems(f"{pin.get('title', '')} {description} {pin.get('alt_text', '')}")
    if wanted and not any(w <= stems for w in wanted):
        return _result("keyword_use", REVIEW, "Ключевая фраза не отражена в тексте пина: проверьте, что пин о том же.")
    return _result("keyword_use", PASS, "Ключевая фраза из исследования отражена в тексте без набивки.")


def check_claims(pin: dict, ctx: CheckContext) -> dict:
    text = " ".join(str(pin.get(k) or "") for k in ("title", "description", "alt_text"))
    block = _BLOCK_CLAIM.search(text)
    if block:
        return _result("claims", BLOCK, f"Обещание результата или абсолютная формулировка «{block.group(0).strip()}» не подтверждена источником.")
    unsourced = [m.group(0).strip() for m in _UNSOURCED.finditer(text)
                 if not ctx.product_facts or m.group(0).strip().casefold()[:5] not in ctx.product_facts.casefold()]
    if unsourced:
        return _result("claims", BLOCK, f"«{unsourced[0]}»: скидки, акции, отзывы и «эксклюзив» нельзя придумывать, их нет в карточке товара.")
    review = [m.group(0).strip() for m in _REVIEW_CLAIM.finditer(text)]
    numbers = [m.group(0).strip() for m in _NUMBER_UNIT.finditer(text)]
    unverified = [n for n in numbers if not ctx.product_facts or n.casefold() not in ctx.product_facts.casefold()]
    if review:
        return _result("claims", REVIEW, f"Превосходная степень, скидка или акция «{review[0]}»: нужно подтверждение на странице товара.")
    if unverified:
        reason = "карточка товара не привязана" if not ctx.product_facts else "в карточке товара этого нет"
        return _result("claims", REVIEW, f"Числовое утверждение «{unverified[0]}» нельзя сверить: {reason}.")
    return _result("claims", PASS, "Обещаний результата, скидок и превосходных степеней в тексте нет.")


def check_destination_url(pin: dict) -> dict:
    url = (pin.get("destination_url") or "").strip()
    if not url:
        return _result("destination_url", REVIEW, "Ссылка назначения не задана.")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        return _result("destination_url", BLOCK, "Ссылка должна начинаться с http:// или https:// и содержать адрес сайта.")
    if parsed.username or parsed.password or "@" in parsed.netloc:
        return _result("destination_url", BLOCK, "В ссылке есть логин или «@»: так маскируют адрес назначения.")
    if host in SHORTENERS or any(host.endswith("." + s) for s in SHORTENERS):
        return _result("destination_url", BLOCK, "Сокращатели ссылок скрывают адрес назначения и запрещены правилами.")
    if parsed.scheme == "http":
        return _result("destination_url", REVIEW, "Ссылка без шифрования (http): лучше https.")
    return _result("destination_url", PASS, "Ссылка корректна и не скрывает адрес назначения.")


def check_duplicates(pin: dict, ctx: CheckContext) -> dict:
    mine = f"{pin.get('title', '')} {pin.get('description', '')}"
    title = (pin.get("title") or "").strip().casefold()
    best = 0.0
    for other in ctx.other_texts:
        if title and other.split("\n", 1)[0].strip().casefold() == title:
            return _result("duplicates", BLOCK, "Точный повтор заголовка другого пина этого бизнеса.")
        best = max(best, similarity(mine, other.replace("\n", " ")))
    if best >= DUPLICATE_BLOCK:
        return _result("duplicates", BLOCK, f"Почти повтор другого пина этого бизнеса (сходство слов {best:.0%}).")
    if best >= DUPLICATE_REVIEW:
        return _result("duplicates", REVIEW, f"Похож на другой пин этого бизнеса (сходство слов {best:.0%}): убедитесь, что идея отличается.")
    return _result("duplicates", PASS, "Среди других пинов этого бизнеса в системе повторов нет.")


def check_alt_text(pin: dict) -> dict:
    alt = (pin.get("alt_text") or "").strip()
    if len(alt) < 10:
        return _result("alt_text", REVIEW, "Альтернативный текст отсутствует или слишком короткий.")
    if alt.count(",") >= 4:
        return _result("alt_text", REVIEW, "Альтернативный текст похож на список ключевых слов, а не на описание изображения.")
    return _result("alt_text", PASS, "Альтернативный текст задан.")


def run_checks(pin: dict, ctx: CheckContext) -> list[dict]:
    """Every check runs; the order is the order shown to the user."""
    return [
        check_text_present(pin),
        check_text_limits(pin, ctx),
        check_strategy_match(pin, ctx),
        check_keyword_use(pin, ctx),
        check_claims(pin, ctx),
        check_destination_url(pin),
        check_duplicates(pin, ctx),
        check_alt_text(pin),
        _result("product_source", NOT_CHECKED if not ctx.product_facts else PASS,
                "Карточка товара не привязана: соответствие товару не проверено." if not ctx.product_facts
                else "Карточка товара привязана; числа и обещания сверены с ней."),
        _result("url_reachable", NOT_CHECKED, "Доступность страницы и цепочку переадресаций проверяют перед публикацией."),
        _result("account_history", NOT_CHECKED, "История опубликованных пинов аккаунта не загружена: повтор с ними не проверен."),
        _result("semantic_review", NOT_CHECKED, "Соответствие правилам сообщества по смыслу и качество изображения автоматически не проверены."),
    ]


def verdict(checks: list[dict]) -> tuple[str, list[str]]:
    """BLOCK if any check blocks, REVIEW if any needs a human, else PASS; plus the ids that were not checked."""
    statuses = {c["status"] for c in checks}
    open_checks = [c["id"] for c in checks if c["status"] == NOT_CHECKED]
    return ("BLOCK" if BLOCK in statuses else "REVIEW" if REVIEW in statuses else "PASS"), open_checks
