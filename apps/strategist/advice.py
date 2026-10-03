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


FOLLOWUP = re.compile(r"вывод|что\s+(?:делать|хорошо|плохо|с\s+этим)|как\s+улучш|где\s+(?:ответ|статист)|рекомендац", re.I)


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
