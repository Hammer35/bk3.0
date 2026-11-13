"""Deterministic analytics and conservative advice applicability checks."""
import math
import re
from datetime import date, timedelta


def local_knowledge_context(query, *, project_root, today):
    """Small lexical fallback for approved sources when embeddings are unavailable."""
    from apps.knowledge.chunking import chunk_markdown
    from apps.knowledge.sources import load_approved_sources

    terms = {w[:5] for w in re.findall(r"[а-яёa-z]{4,}", query.casefold())}
    case_requested = bool(re.search(r"кейс|пример|опыт|практик", query, re.I))
    ranked = []
    directory = project_root / "docs" / "ai-knowledge" / "knowledge"
    for source in load_approved_sources(directory, project_root=project_root):
        if source.language != "ru" or not source.source_checked or source.source_checked > today:
            continue
        if source.effective_until and source.effective_until < today:
            continue
        for chunk in chunk_markdown(source.content, max_chars=1800, overlap_chars=0):
            words = {w[:5] for w in re.findall(r"[а-яёa-z]{4,}", chunk.content.casefold())}
            score = len(terms & words)
            if case_requested and "Pink Seed" in chunk.heading:
                score += 10
            if score:
                ranked.append((score, source, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return "\n\n".join(
        f"Проверенный материал: {source.title} / {chunk.heading}\n{chunk.content}\n"
        f"Источники: {', '.join(source.source_links)}"
        for _, source, chunk in ranked[:2]
    )


def comparison_issues(current, previous, period, previous_period, *, today):
    """Require evidence of complete, equally long periods before diagnosing change."""
    issues = []
    if period[1] >= today:
        issues.append("Текущий день по UTC ещё не завершён.")
    if not previous or not previous_period:
        issues.append("Нет данных предыдущего равного периода.")
    elif period[1] - period[0] != previous_period[1] - previous_period[0]:
        issues.append("Продолжительность сравниваемых периодов различается.")
    for label, response, dates in (("Текущий", current, period), ("Предыдущий", previous, previous_period)):
        if not response or not dates:
            continue
        expected = {str(dates[0] + timedelta(days=i)) for i in range((dates[1] - dates[0]).days + 1)}
        groups = [g for g in response.values() if isinstance(g, dict) and "summary_metrics" in g]
        if not groups:
            issues.append(f"{label} период: нет итоговых показателей.")
            continue
        for group in groups:
            ready = set()
            for row in group.get("daily_metrics", []) or []:
                if not isinstance(row, dict):
                    continue
                status = row.get("data_status")
                if isinstance(status, dict):
                    status = status.get("value")
                if status == "READY":
                    ready.add(str(row.get("date")))
            if not expected.issubset(ready):
                issues.append(f"{label} период: полнота окончательных данных за каждый день не подтверждена.")
                break
    return issues


FOLLOWUP = re.compile(r"вывод|что\s+(?:делать|хорошо|плохо|с\s+этим)|как\s+улучш|где\s+(?:ответ|статист)|рекомендац|что\s+проверить|почему\s+(?:вырос|упал|сниз|стало|больше|меньше)\w*\s+(?:показ|клик|переход|сохран)|причин\w*[^.!?]{0,30}(?:показ|клик|переход|сохран)", re.I)


def analytics_followup_context(message, history):
    if not FOLLOWUP.search(message):
        return None
    if re.search(r"\b(?:сайт|страниц|код|utm|реклам|карусел|заголов|дизайн|оформлен)", message, re.I):
        return None
    # An explicit account starts its own request, never silently substitute it.
    if re.search(r"@[A-Za-z0-9._-]+", message):
        return None
    for item in history:
        if item["role"] == "USER" and not FOLLOWUP.search(item["content"]):
            return None
        if item["role"] != "ASSISTANT":
            continue
        if item["provider"] != "pinterest-api" or item["model"] != "direct-read":
            continue
        match = re.match(r"Органика @([A-Za-z0-9._-]+)\s+(?:Период:\s*)?(\d{4}-\d{2}-\d{2})\s*—\s*(\d{4}-\d{2}-\d{2})", item["content"])
        if match:
            try:
                return match[1], (date.fromisoformat(match[2]), date.fromisoformat(match[3]))
            except ValueError:
                return None
        return None
    return None


ADVICE_RULES = (
    "Ограничения рекламного кабинета относятся только к платному продвижению. "
    "Не упоминай кабинет, страну, оплату, ads:read или ROI, если пользователь спрашивает "
    "об органических Pins, CTA или правилах Pinterest. Не переключай такой ответ на тему рекламы. "
    "Сам не предлагай платное продвижение. Если пользователь просит спланировать или запустить "
    "платную рекламу, сначала проверь кабинет, страну, оплату и доступ приложения; без этих данных "
    "не рекомендуй запуск. Не предлагай неподтверждённые рекламные форматы. "
    "Не рассчитывай ROI без расходов, выручки и правил атрибуции. Не утверждай, что сайт "
    "медленный или неудобный, без измерений. UTM — параметры целевых ссылок; они не измеряют "
    "продажи без настроенной аналитики. Не объявляй видео неэффективным по доле просмотров "
    "среди показов всех форматов. Для персональных рекомендаций по статистике укажи "
    "наблюдение, гипотезу, одно действие и метрику проверки. "
    "Практический опыт подтверждай найденным кейсом со ссылкой и условиями; если такого "
    "источника нет, не выдавай общий совет за доказанную практику. Чужой рост не является "
    "нормой или обещанием. Сравнение органических пинов не называй рандомизированным A/B-тестом."
)


def _asks_for_paid_ad_recommendation(message: str) -> bool:
    normalized = str(message or "").casefold()
    if re.search(r"правил|запрещ|разреш|cta|призыв|формулиров|политик|спам", normalized):
        return False
    action = r"(?:запуст|запуск|настрой|спланируй|составь|подготовь|создай|предложи|рекоменд|посовет|подбери|стратег|план|бюджет|стоит ли)\w*"
    topic = r"(?:реклам\w*|\bads?\b|платн.{0,15}продвиж\w*)"
    action_before_topic = re.search(rf"{action}[^.!?]{{0,60}}{topic}", normalized)
    topic_before_action = re.search(rf"{topic}[^.!?]{{0,60}}{action}", normalized)
    return bool(action_before_topic or topic_before_action)


def enforce_advice_boundaries(content, *, request_message=None):
    """Conservative final gate until the product can verify advertising eligibility.

    Paid-ad eligibility checks should not affect organic Pins or neutral policy questions.
    """
    if request_message is not None and not _asks_for_paid_ad_recommendation(request_message):
        unsupported_format = re.compile(r"карусел|carousel|\bquiz\b|мини[- ]?игр", re.I)
        return "\n\n".join(
            paragraph for paragraph in re.split(r"\n\s*\n", content)
            if not unsupported_format.search(paragraph)
        )

    restricted = re.compile(r"карусел|carousel|\bquiz\b|мини[- ]?игр|\bопрос|реклам|\bROI\b|\bROAS\b", re.I)
    replacement = (
        "Рекламный кабинет, его страна и доступ к рекламе не проверены. Поэтому рекомендовать "
        "запуск рекламы или рекламные форматы сейчас нельзя. Подключение Pinterest-профиля "
        "не подтверждает эти условия. Уточните наличие кабинета и его страну, если хотите "
        "обсуждать рекламу. Данных о расходах и продажах для расчёта окупаемости нет."
    )
    parts, inserted = [], False
    for paragraph in re.split(r"\n\s*\n", content):
        if restricted.search(paragraph):
            if not inserted:
                parts.append(replacement)
                inserted = True
        else:
            parts.append(paragraph)
    return "\n\n".join(parts)

def enforce_creative_answer(content, *, request_message):
    """Keep a single proposed caption when the model adds unsolicited commentary."""
    if (not re.search(r"^(?:предложи|придумай|напиши|дай|составь)\b", request_message, re.I)
            or not re.search(r"\bcta\b|подпис\w*", request_message, re.I)
            or re.search(r"правил|запрещ|разреш|проверь|вариант|несколько|можно", request_message, re.I)
            or re.search(r"не могу|нельзя|не рекомендую|не используй|запрещ", content, re.I)):
        return content
    # Only the familiar intro + quoted proposal shape; leave refusals and
    # unstructured responses intact instead of extracting an arbitrary quote.
    proposal = re.search(r"^(?:Вот|Предлагаю)[^\n]*\n\s*[«\"]([^»\"\n]{1,400})[»\"]", content)
    return proposal.group(1) if proposal else content


def enforce_source_honesty(content):
    """Correct unsupported claims without deleting warnings or quoted examples.

    This gate covers a bounded set of recurring errors, not factual verification
    of arbitrary model answers. Official text limits use a fresh approved source.
    """
    from .grounded_answers import approved_pin_text_limits

    limits = approved_pin_text_limits()
    parts = []
    for paragraph in re.split(r"\n\s*\n", content):
        def replace_uniqueness(match):
            sentence = match.group(0)
            if re.search(r'не\s+(?:обещ|пиши|пишите|утвержд|использ)|избег|нельзя|без\s+доказ|[«"“]', sentence, re.I):
                return sentence
            return re.match(r"\s*", sentence).group(0) + "Уникальность товара без сравнения с аналогами не подтверждена."

        paragraph = _UNSUPPORTED_UNIQUENESS.sub(replace_uniqueness, paragraph)
        paragraph = re.sub(r"\bуникальн\w+\s+(товар\w*|продукт\w*|издели\w*)", r"\1", paragraph, flags=re.I)
        sentences = re.split(r"(?<=[.!?])(\s+)", paragraph)
        corrected = []
        for sentence in sentences:
            if _LENGTH_NORM.search(sentence) and _NORM_FRAMING.search(sentence) and not _NORM_CAVEAT_PRESENT.search(paragraph):
                # A recommendation about an ideal length is never a maximum.
                official_max = False
                numbers = re.findall(r"\b\d+\b", sentence)
                for field, maximum in limits.items():
                    if (re.search(field, sentence, re.I) and numbers == [str(maximum)]
                            and re.search(r"до\s+\d|максим|лимит", sentence, re.I)
                            and not re.search(r"оптимальн|идеальн|рекоменду|лучшая", sentence, re.I)):
                        official_max = True
                if not official_max:
                    if re.search(r"Pinterest|пинтерест|официальн|требован|правил", sentence, re.I):
                        sentence = "Не могу подтвердить эту длину как официальное требование Pinterest."
                    sentence = f"{sentence.rstrip()} {_LENGTH_NORM_CAVEAT}"
            corrected.append(sentence)
        paragraph = "".join(corrected)
        if (_PERMISSION_VERDICT.search(paragraph) and _WORDING_TOPIC.search(paragraph)
                and not _VERDICT_LIMIT.search(paragraph)
                and not re.search(r"длин|лимит|символ|спам", paragraph, re.I)):
            paragraph = f"{paragraph.rstrip()}\n\n{_CTA_VERDICT_LIMIT}"
        parts.append(paragraph)
    return "\n\n".join(parts)


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
    r"рекоменду\w*|треб\w*|официальн\w*|лимит\w*|оптимальн\w*|идеальн\w*|лучшая\s+длина|"
    r"следует\s+использовать|нужно\s+\d|полностью\s+отображал",
    re.I,
)

_NORM_CAVEAT_PRESENT = re.compile(
    r"эвристик|не (?:указан|закреплён|закреплен)|официальн\w*\s+(?:требован|норма|лимит)\s+не",
    re.I,
)

_LENGTH_NORM_CAVEAT = (
    "Это практическая эвристика, а не официальное требование Pinterest."
)


_WORDING_TOPIC = re.compile(
    r"призыв|\bcta\b|фраз|слов|текст|описани|заголовок|подпись",
    re.I,
)


def metric_value(summary: dict, name: str) -> int | float | None:
    value = summary.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return value


def format_metric_number(value: int | float) -> str:
    return str(int(value)) if value == int(value) else f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def analytics_advice(summary: dict, previous: dict | None) -> tuple[list[str], list[str], list[str]]:
    """Find observable weak points and suggest checks without inventing causes."""
    previous = previous or {}
    improvements = []
    observations = []
    actions = []
    impressions = metric_value(summary, "IMPRESSION")
    previous_impressions = metric_value(previous, "IMPRESSION")

    if impressions == 0:
        observations.append("Pinterest не зафиксировал показов за период; эффективность пинов оценить нельзя.")
        actions.append(
            "Проверьте выбранный период, доступность опубликованных пинов и полноту данных. "
            "Повторите оценку после появления показов."
        )
    elif impressions is not None and previous_impressions is not None and impressions < previous_impressions:
        observations.append(
            f"Показы снизились: {format_metric_number(previous_impressions)} → "
            f"{format_metric_number(impressions)}. По общей статистике причина не видна."
        )
        actions.append(
            "Сравните число опубликованных пинов и темы за оба периода. Найдите темы с просадкой "
            "и сравните отдельные пины сопоставимого возраста и формата. Проверяйте одну гипотезу за раз; изменение показов само по себе не доказывает причину."
        )
    elif impressions is not None and previous_impressions is not None and impressions > previous_impressions:
        improvements.append(
            f"Показы выросли: {format_metric_number(previous_impressions)} → {format_metric_number(impressions)}."
        )
    rate_checks = (
        (
            "OUTBOUND_CLICK", "Доля исходящих кликов", "Исходящие клики",
            "Проверьте ссылку и соответствие страницы обещанию пина. Для следующего оригинального "
            "пина укажите понятную причину перейти по ссылке; сравните исходящие клики на 100 показов.",
        ),
        (
            "PIN_CLICK", "Доля открытий пина", "Открытия пина",
            "Проверьте на следующих оригинальных пинах одной темы более ясный заголовок. "
            "Сравните открытия на 100 показов у пинов одной темы, формата и возраста. Это проверка гипотезы, а не доказательство причины.",
        ),
        (
            "SAVE", "Доля сохранений", "Сохранения",
            "Добавьте в следующий оригинальный пин конкретную полезную информацию по теме. "
            "Сравните сохранения на 100 показов у сопоставимых пинов. Это гипотеза; гарантировать рост нельзя.",
        ),
    )
    for metric, label, count_label, action in rate_checks:
        current_count = metric_value(summary, metric)
        previous_count = metric_value(previous, metric)
        if (
            impressions is None or impressions <= 0 or previous_impressions is None
            or previous_impressions <= 0 or current_count is None or previous_count is None
        ):
            continue
        current_rate = current_count / impressions * 100
        previous_rate = previous_count / previous_impressions * 100
        if current_rate < previous_rate:
            observations.append(
                f"{label} снизилась: {format_metric_number(previous_rate)}% → "
                f"{format_metric_number(current_rate)}% ({count_label.lower()} на 100 показов)."
            )
            actions.append(action)
        elif current_rate > previous_rate:
            improvements.append(
                f"{label} выросла: {format_metric_number(previous_rate)}% → "
                f"{format_metric_number(current_rate)}%."
            )

    pin_clicks = metric_value(summary, "PIN_CLICK")
    saves = metric_value(summary, "SAVE")
    outbound_clicks = metric_value(summary, "OUTBOUND_CLICK")
    if (
        impressions is not None and impressions > 0 and pin_clicks == 0
        and not any("Доля открытий пина" in item for item in observations)
    ):
        observations.append(f"При {format_metric_number(impressions)} показах Pinterest не зафиксировал открытий пина.")
        actions.append(
            "Проверьте, понятны ли тема и заголовок на следующих оригинальных пинах. "
            "Измените один элемент и сравните открытия на 100 показов; ноль сам по себе не объясняет причину."
        )
    if (
        impressions is not None and impressions > 0 and saves == 0
        and not any("Доля сохранений" in item for item in observations)
    ):
        observations.append(f"При {format_metric_number(impressions)} показах Pinterest не зафиксировал сохранений.")
        actions.append(
            "Проверьте, даёт ли следующий оригинальный пин конкретную пользу по заявленной теме. "
            "Сравните сохранения на 100 показов; причина нуля из общей статистики неизвестна."
        )
    if pin_clicks is not None and pin_clicks > 0 and outbound_clicks == 0:
        if not any("исходящих кликов" in item.casefold() for item in observations):
            observations.append(
                "Пины открывали, но Pinterest не зафиксировал исходящих кликов. "
                "Данные не показывают причину."
            )
        if not any("проверьте ссылку" in item.casefold() for item in actions):
            actions.append(
                "Проверьте ссылку и соответствие страницы обещанию пина. Для следующего оригинального "
                "пина укажите понятную причину перейти по ссылке; сравните исходящие клики."
            )

    return improvements[:4], observations[:4], actions[:4]


def analytics_explanation(summary, previous, *, metric="OUTBOUND_CLICK", comparable=False):
    """Explain trusted numeric data without making causal or significance claims."""
    labels = {"IMPRESSION": "Показы", "OUTBOUND_CLICK": "Исходящие клики", "SAVE": "Сохранения"}
    label = labels[metric]
    current = metric_value(summary, metric)
    old = metric_value(previous or {}, metric) if comparable else None
    if current is None:
        fact = f"{label}: значение недоступно; это не ноль."
    elif old is None:
        fact = f"{label}: {format_metric_number(current)}. Сопоставимая динамика не подтверждена."
    else:
        fact = f"{label}: {format_metric_number(old)} → {format_metric_number(current)}."
    if comparable and metric != "IMPRESSION":
        current_impressions = metric_value(summary, "IMPRESSION")
        old_impressions = metric_value(previous or {}, "IMPRESSION")
        if current is not None and old is not None and current_impressions and old_impressions:
            fact += (
                f" На 100 показов: {format_metric_number(old / old_impressions * 100)}% → "
                f"{format_metric_number(current / current_impressions * 100)}%."
            )
    limit = "Причина изменения по общей статистике не установлена."
    if not comparable:
        action = "Сначала получите полные данные за два равных завершённых периода."
    elif metric == "IMPRESSION":
        action = "Одна проверка: сравните показы отдельных пинов одной темы, формата и возраста за эти периоды."
    else:
        action = f"Одна проверка: сравните {label.lower()} на 100 показов у отдельных пинов одной темы, формата и возраста."
    return f"{fact}\n{limit}\n{action}"


_FAKE_ACTION = re.compile(
    r"(?:стратеги\w+|план\w*|контент\w*)\s+(?:уже\s+)?(?:запущен\w*|опубликован\w*|сохранен\w*|сохранён\w*)|"
    r"\b(?:приступаю\s+к\s+реализации|запускаю\s+(?:стратегию|публикаци\w+)|начинаю\s+публикаци\w+|"
    r"публикую\s+(?:пин\w*|контент)|запустил\w*\s+(?:стратегию|публикаци\w+))", re.I)
FAKE_ACTION_NOTE = (
    "Важно: я ничего не запускал, не публиковал и не сохранял. Это текст-рассуждение, а не созданная стратегия. "
    "Чтобы получить сохранённую стратегию, напиши «Построй стратегию»."
)


def enforce_no_fake_actions(content):
    """The chat model cannot launch or publish anything; correct replies that claim it did."""
    if not isinstance(content, str) or FAKE_ACTION_NOTE in content or not _FAKE_ACTION.search(content):
        return content
    return f"{content.rstrip()}\n\n{FAKE_ACTION_NOTE}"
