# Текущий участок advice.py

```python
def enforce_source_honesty(content):
    """Return the model answer when it dropped a limit stated in its own material.

    Retrieved knowledge states what it does not establish: that a verdict about
    CTA wording is an inference from published rules and not Pinterest approval
    of the exact text. The model reliably reproduces the substance and drops the
    limit, which reads to the user as authority. The limit is appended when a
    permission verdict is given without it. Unique-selling-point claims are
    removed: no source can establish them, and the knowledge forbids promising
    uniqueness.
    """
    parts, changed = [], False
    for paragraph in re.split(r"\n\s*\n", content):
        if _UNSUPPORTED_UNIQUENESS.search(paragraph):
            sentence_stripped = _UNSUPPORTED_UNIQUENESS.sub("", paragraph)
            if sentence_stripped.strip():
                parts.append(sentence_stripped)
            changed = True
            continue
        parts.append(paragraph)
    text = "\n\n".join(parts)

    if _PERMISSION_VERDICT.search(text) and _WORDING_TOPIC.search(text) and not _VERDICT_LIMIT.search(text):
        text = f"{text.rstrip()}\n\n{_CTA_VERDICT_LIMIT}"
        changed = True

    if _LENGTH_NORM.search(text) and _NORM_FRAMING.search(text) and not _NORM_CAVEAT_PRESENT.search(text):
        text = f"{text.rstrip()}\n\n{_LENGTH_NORM_CAVEAT}"
        changed = True
    return text if changed else content


_CTA_VERDICT_LIMIT = (
    "Это вывод из опубликованных правил, а не решение модерации Pinterest по конкретной "
    "фразе: правила могут измениться, а текст до публикации никто не проверял."
)

_UNSUPPORTED_UNIQUENESS = re.compile(
    r"[^.!?\n]*\b(?:нет ни у кого|не имеет аналогов|аналогов нет|"
    r"единственн(?:ый|ая|ое|ые|ую)\s+в\s+(?:мире|стране|каталоге|сервисе))[^.!?\n]*[.!?]?",
    re.I,
)

_PERMISSION_VERDICT = re.compile(
    r"(?:Pinterest|пинтарест)\s+(?:разрешает|одобряет|не\s+запрещает|запрещает)|"
    r"\bне\s+запрещ[её]н\b|\bможно\s+(?:использовать|писать|указывать)\b",
    re.I,
)

_VERDICT_LIMIT = re.compile(
    r"вывод из|не (?:решение|одобрение|одобрения)|не подтвержда[её]т одобрени|"
    r"никто не проверял|может измениться",
    re.I,
)


_LENGTH_NORM = re.compile(r"\b\d+\s*(?:символ\w*|слов\w*|знаков)", re.I)

_NORM_FRAMING = re.compile(
    r"рекоменду\w*|треб\w*|оптимальн\w*|идеальн\w*|лучшая\s+длина|"
    r"следует\s+использовать|нужно\s+\d|полностью\s+отображал",
    re.I,
)

_NORM_CAVEAT_PRESENT = re.compile(
    r"эвристик|не (?:указан|закреплён|закреплен)|официальн\w*\s+(?:требован|норма|лимит)\s+не",
    re.I,
)

_LENGTH_NORM_CAVEAT = (
    "Точный лимит длины в найденной справке не указан: это практическая эвристика, "
    "а не официальное требование Pinterest. Ограничения лучше проверить в самом "
    "редакторе Pin."
)

_WORDING_TOPIC = re.compile(
    r"призыв|\bcta\b|фраз|слов|текст|описани|заголовок|подпись",
    re.I,
)


```
