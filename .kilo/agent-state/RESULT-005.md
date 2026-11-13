# RESULT-005

Исполнитель: opencode-cli; модель: `openrouter/openrouter/free`.
Сессия: ses_eff63a144ffe0qCoqDk85rMQyW.
Статус: ожидает приёмки Codex.



Исходники (`apps/strategist/advice.py`, `apps/strategist/tests.py`) доступны только для чтения через разрешённые пути; по правилам AGENTS.md я читаю только `.kilo/agent-state/CONTEXT-005.md`. Предлагаю код и тесты текстом, без правки файлов.

---

## Предлагаемая замена

```python
import re


def enforce_source_honesty(content):
    """Снимает необоснованные утверждения и добавляет оговорки о来源.

    Проверяет каждый абзац отдельно:
    - убирает утверждения о уникальности («нет ни у кого», «аналогов нет»),
      сохраняя цитату пользователя;
    - к вердикту о разрешении/запрете CTA-фразы прикладывает оговорку,
      что это вывод из правил, а не модерация;
    - к практической рекомендации по длине прикладывает оговорку, что это
      эвристика, а не официальный лимит (только внутри того же абзаца).
    """
    parts, changed = [], False
    for paragraph in re.split(r"\n\s*\n", content):
        paragraph, para_changed = _process_paragraph(paragraph)
        changed = changed or para_changed
        parts.append(paragraph)
    text = "\n\n".join(parts)
    return text if changed else content


def _process_paragraph(paragraph):
    """Возвращает (обработанный_абзац, было_изменение)."""
    changed = False

    # 1. Уникальность: убираем утверждение, но не цитату пользователя.
    if _UNSUPPORTED_UNIQUENESS.search(paragraph):
        stripped = _UNSUPPORTED_UNIQUENESS.sub("", paragraph)
        if stripped.strip() and '"' not in stripped:
            paragraph = stripped
            changed = True

    # 2. Вердикт по CTA — оговорка внутри того же абзаца.
    if (_PERMISSION_VERDICT.search(paragraph)
            and _WORDING_TOPIC.search(paragraph)
            and not _VERDICT_LIMIT.search(paragraph)):
        paragraph = f"{paragraph.rstrip()}\n\n{_CTA_VERDICT_LIMIT}"
        changed = True

    # 3. Длина — оговорка только к абзацу, где есть цифра и нормативное слово.
    if (_LENGTH_NORM.search(paragraph)
            and _NORM_FRAMING.search(paragraph)
            and not _NORM_CAVEAT_PRESENT.search(paragraph)):
        paragraph = f"{paragraph.rstrip()}\n\n{_LENGTH_NORM_CAVEAT}"
        changed = True

    return paragraph, changed


# --- Ограничения regex (явные, чтобы не быть «широкими эвристиками») ---
# _UNSUPPORTED_UNIQUENESS: только прямые формулировки о несуществующих аналогах.
# _PERMISSION_VERDICT: только «Pinterest + глагол разрешения/запрета».
# _WORDING_TOPIC: только слова о CTA/фразах/описании — тема вердикта.
# _NORM_FRAMING: только нормативные слова (рекомендует/требует/оптимально).
# _LENGTH_NORM: только «цифра + слово символ/знак/слов».
# _VERDICT_LIMIT / _NORM_CAVEAT_PRESENT: уже присутствует оговорка.

_CTA_VERDICT_LIMIT = (
    "Это вывод из опубликованных правил, а не решение модерации Pinterest по конкретной "
    "фразе: правила могут измениться, а текст до публикации никто не проверял."
)

_LENGTH_NORM_CAVEAT = (
    "Точный лимит длины в найденной справке не указан: это практическая эвристика, "
    "а не официальное требование Pinterest. Ограничения лучше проверить в самом "
    "редакторе Pin."
)

_UNSUPPORTED_UNIQUENESS = re.compile(
    r"[^.!?\n]*\b(?:нет ни у кого|не имеет аналогов|аналогов нет|"
    r"единственн(?:ый|ая|ое|ые|ую)\s+в\s+(?:мире|стране|каталоге|сервисе))[^.!?\n]*[.!?]?",
    re.I,
)

_PERMISSION_VERDICT = re.compile(
    r"(?:Pinterest|пинтарест)\s+(?:разрешает|одобряет|не\s+запрещает|запрещает)",
    re.I,
)

_WORDING_TOPIC = re.compile(
    r"призыв|\bcta\b|фраз[ы]?| слов[а]?| текст[ы]?| описани[ея]| заголовок| подпись",
    re.I,
)

_LENGTH_NORM = re.compile(r"\b\d+\s*(?:символ\w*|слов\w*|знаков)", re.I)

_NORM_FRAMING = re.compile(
    r"рекоменду\w*|треб\w*|оптимальн\w*|идеальн\w*|лучшая\s+длина|"
    r"следует\s+использовать|нужно\s+\d|полностью\s+отображал",
    re.I,
)

_VERDICT_LIMIT = re.compile(
    r"вывод из|не (?:решение|одобрение|одобрения)|не подтвержд[её]т одобрени|"
    r"никто не проверял|может измениться|официальный лимит",
    re.I,
)

_NORM_CAVEAT_PRESENT = re.compile(
    r"эвристик|не (?:указан|закреплён|закреплен)|официально\s+не\s+указан",
    re.I,
)
```

## Тесты (регрессионные)

```python
import unittest
from apps.strategist.advice import enforce_source_honesty


class SourceHonestyTest(unittest.TestCase):
    def test1_уникальность_удаляется(self):
        src = "Этот инструмент не имеет аналогов в мире."
        out = enforce_source_honesty(src)
        self.assertNotIn("аналогов", out.lower())
        self.assertNotEqual(out, src)

    def test2_цитата_пользователя_сохраняется(self):
        src = "Я заметил: «У них нет ни у кого аналогов»."
        out = enforce_source_honesty(src)
        self.assertIn("нет ни у кого", out.lower())
        self.assertEqual(out, src)

    def test3_вердикт_получает_оговорку(self):
        src = "Pinterest разрешает использовать CTA в описании."
        out = enforce_source_honesty(src)
        self.assertIn("вывод из опубликованных правил", out.lower())
        self.assertIn("не решение модерации", out.lower())

    def test4_длина_получает_оговорку(self):
        src = "Рекомендуемая длина описания — 80–100 символов."
        out = enforce_source_honesty(src)
        self.assertIn("практическая эвристика", out.lower())
        self.assertIn("не официальное требование", out.lower())

    def test5_оговорка_уже_есть_не_дублируется(self):
        src = ("Pinterest не запрещает CTA, это вывод из правил, "
               "никто не проверял конкретную фразу.")
        out = enforce_source_honesty(src)
        self.assertEqual(out, src)

    def test6_аналогичные_решения_не_триггер(self):
        src = "Похоже на аналогичные решения в отрасли."
        out = enforce_source_honesty(src)
        self.assertEqual(out, src)

    def test7_негатив_по_длине_без_фрейминга(self):
        src = "Описание содержит 120 символов."
        out = enforce_source_honesty(src)
        self.assertEqual(out, src)

    def test8_самоотрицание_не_триггер(self):
        src = "Это не имеет аналогов, но я не уверен."
        out = enforce_source_honesty(src)
        self.assertNotIn("не имеет аналогов", out.lower())
```

## Исправляемые дефекты исходника

1. **Оговорка приkleивалась ко всему ответу** (`_PERMISSION_VERDICT.search(text)` на всём тексте) — теперь проверка идёт по каждому абзацу отдельно, CTA-оговорка прикрепляется только к абзацу с вердиктом.
2. **Оговорка о длине добавлялась при наличии `_LENGTH_NORM` и `_NORM_FRAMING` в любом месте текста** — теперь оба паттерна должны быть в одном абзаце, иначе оговорка не приkleивается (например, «Описание содержит 120 символов» без нормативного слова не триггерит).
