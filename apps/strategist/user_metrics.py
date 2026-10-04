"""Conservative calculations for counts explicitly supplied in the current question.

This is a bounded text parser, not a source of account data. Unclear attribution
is clarified instead of asking a model to guess numbers or causal explanations.
"""
import re
from decimal import Decimal, InvalidOperation

from .advice import format_metric_number

_METRIC = re.compile(r"\b(?:показ(?:ы|ов|а|ах|ами)?\b|переход\w*|(?:исходящ\w*\s+)?клик\w*|заказ\w*|покуп\w*|сохранени\w*|публикаци\w*|пинов?\b)", re.I)
_NUMBER = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[,.]\d+)?(?:\s*(?:тыс\.?|млн))?(?!\w)", re.I)
_PAIR = re.compile(rf"({_METRIC.pattern})\s*[:=]?\s*({_NUMBER.pattern})|({_NUMBER.pattern})\s*({_METRIC.pattern})", re.I)
_PERIOD = re.compile(r"\b(?:за\s+(?:последни\w*\s+)?|последни\w*\s+)(\d+)\s*(дн\w*|день|недел\w*|месяц\w*)", re.I)
_EXCLUDE = re.compile(r"придумай|напиши|создай|сгенерируй|\bпокажи\b|выгрузи|получи\s+данные|подпись|правил|политик|разреш|запрещ|\bcta\b|накрут|спам|обойти|взлом|игнорируй|забудь\s+правила", re.I)
_LABELS = {"impressions": "Показы", "clicks": "Переходы", "orders": "Заказы", "saves": "Сохранения", "posts": "Публикации"}
_CLARIFY = "Уточни, какое число относится к какой метрике и периоду: например, «за прошлую неделю: показы …, переходы …; за текущую: показы …, переходы …»."


def _kind(word):
    word = word.casefold()
    if word.startswith("показ"):
        return "impressions"
    if word.startswith(("заказ", "покуп")):
        return "orders"
    if word.startswith("сохран"):
        return "saves"
    if word.startswith(("публикац", "пин")):
        return "posts"
    return "clicks"


def _integer(raw):
    normalized = re.sub(r"[ \u00a0\u202f]", "", raw.casefold())
    multiplier = 1
    if re.search(r"тыс\.?$", normalized):
        multiplier = 1000
        normalized = re.sub(r"тыс\.?$", "", normalized)
    elif normalized.endswith("млн"):
        multiplier = 1000000
        normalized = normalized[:-3]
    try:
        value = Decimal(normalized.replace(",", ".")) * multiplier
    except InvalidOperation:
        return None
    if value < 0 or value != value.to_integral_value() or value > 10**12:
        return None
    return int(value)


def _counts(text):
    """Return ordered counts only when a clause has exactly one metric kind."""
    result = {}
    for clause in re.split(r"[;!?\n]|\.(?!\d)|,\s*(?:а|но)\s+|\s+и\s+(?=(?:ни\s+одного|\d+\s*заказ))", text):
        clause = re.sub(r"^\s*(?:(?:за\s+)?(?:прошл\w*|предыдущ\w*|текущ\w*)\s+(?:недел\w*|месяц\w*|период)\s*:|(?:раньше|теперь)\s*:)\s*", "", clause, flags=re.I)
        clause = re.sub(r"^\s*(?:было|стало)\s+", "", clause, flags=re.I)
        metrics = list(_METRIC.finditer(clause))
        kinds = {_kind(m[0]) for m in metrics}
        if not kinds:
            continue
        # Label:value lists are unambiguous; long prose with several metrics isn't.
        if len(kinds) > 1:
            pairs = list(_PAIR.finditer(clause))
            remainder = _PAIR.sub("", clause)
            if pairs and not re.sub(r"[\s,]|\bи\b", "", remainder, flags=re.I):
                for match in pairs:
                    kind = _kind(match[1] or match[4])
                    value = _integer(match[2] or match[3])
                    if value is None:
                        return None
                    result.setdefault(kind, []).append(value)
                    if len(result[kind]) > 2:
                        return None
                continue
            return None
        kind = kinds.pop()
        period_spans = [m.span(1) for m in _PERIOD.finditer(clause)]
        numbers = []
        for number in _NUMBER.finditer(clause):
            if any(a <= number.start() < b for a, b in period_spans):
                continue
            # Years/IDs/prices are never evidence for this clause's metric.
            if re.match(r"\s*(?:год|руб|₽|артикул|%)", clause[number.end():], re.I):
                return None
            value = _integer(number[0])
            if value is None:
                return None
            numbers.append(value)
        if not numbers and re.search(r"ни\s+одного|ноль", clause, re.I):
            numbers = [0]
        if numbers:
            if re.search(r"не\s+измен|прежн|те\s+же|остал", clause, re.I):
                result.setdefault("constant", []).append(kind)
            if len(numbers) > 2:
                return None
            result.setdefault(kind, []).extend(numbers)
            if len(result[kind]) > 2:
                return None
    return result


def user_metrics_answer(text):
    """Answer a supported numeric observation, clarify ambiguity, or return None.

    No numbers or facts are taken from assistant history or connected accounts.
    Unsupported non-analytics requests continue through the ordinary chat path.
    """
    if len(text) > 2500 or _EXCLUDE.search(text) or not _METRIC.search(text):
        return None
    profile_labels = re.findall(r"(?:перв\w*|втор\w*)\s+(?:(?:pinterest|пинтерест)[ -]*)?(?:аккаунт|профил)", text, re.I)
    if len(profile_labels) > 1 or (profile_labels and re.search(r"во?\s+втор\w*\s+\d", text, re.I)):
        return "Для какого одного профиля разбираем цифры? Укажи его и числа за два сравнимых периода."
    if re.search(r"вчера", text, re.I) and re.search(r"почему", text, re.I):
        return None
    if re.match(r"\s*Цена\b", text, re.I):
        return None
    if not _NUMBER.search(text) or not re.search(
        r"был|стало|упал|вырос|сниз|удво|не\s+измен|выложил|вариант|получается|вывод|значит|сработ|эффектив|причин|что\s+проверить|это\s+хорош|бесполез|изменил|почему|конверт|неделя:|раньше|теперь|(?:показы|переходы|клики|заказы)\s*[:=]\s*\d", text, re.I,
    ):
        return None
    if re.search(r"не\s+помню|неясн|не\s+знаю[^.!?]{0,30}период", text, re.I):
        return _CLARIFY
    if len(set(re.findall(r"@[a-z0-9._-]+", text, re.I))) > 1:
        return "Для какого одного профиля разбираем цифры? Укажи его и числа за два сравнимых периода."
    first_number = _NUMBER.search(text)
    earlier_label = re.search(r"раньше|(?<!\w)до\s*:", text, re.I)
    if earlier_label and earlier_label.start() > first_number.start():
        return _CLARIFY
    past_label = re.search(r"прошл\w*|предыдущ\w*", text, re.I)
    current_label = re.search(r"текущ\w*|теперь", text, re.I)
    if past_label and current_label and current_label.start() < past_label.start():
        return _CLARIFY
    counts = _counts(text)
    if not counts:
        if re.search(r"сколько[^.!?]*заказ", text, re.I) and re.search(r"переход|клик", text, re.I):
            return None
        return _CLARIFY
    source = "По твоим данным: "
    periods = list(_PERIOD.finditer(text))
    durations = {int(m[1]) * (7 if m[2].casefold().startswith("недел") else 1) for m in periods if not m[2].casefold().startswith("месяц")}
    if len(periods) > 1 and (len(durations) > 1 or any(m[2].casefold().startswith("месяц") for m in periods)):
        return ("Сопоставимость этих периодов не подтверждена; по их итогам нельзя утверждать падение или рост. "
                "Если окна перекрываются, среднее за день тоже не доказывает тренд. "
                "Одна проверка: сравни два равных неперекрывающихся завершённых периода.")
    impressions = counts.get("impressions", [])
    clicks = counts.get("clicks", [])
    orders = counts.get("orders", [])
    if len(impressions) == 2 and len(clicks) == 1 and "clicks" in counts.get("constant", []):
        clicks = clicks * 2
    if len(impressions) == 1 and len(clicks) == 2 and "impressions" in counts.get("constant", []):
        impressions = impressions * 2
    if len(impressions) == 2 and len(clicks) == 2:
        if not re.search(r"\b(?:со?\s+\d+|до\s+\d+|был\w*|стал\w*|прошл\w*|текущ\w*|раньше|теперь)\b|→|->", text, re.I):
            return _CLARIFY
        if not all(impressions):
            return source + "при нуле показов долю переходов для этого периода посчитать нельзя. Одна проверка: уточни полноту данных и период с нулём показов."
        before, after = (clicks[i] / impressions[i] * 100 for i in range(2))
        return (source + f"доля переходов {format_metric_number(before)}% → {format_metric_number(after)}%; "
                f"число переходов {clicks[0]} → {clicks[1]}. Причина изменения неизвестна; эта доля не равна конверсии в заказ. "
                "Одна проверка: сравни доли переходов отдельных публикаций при сопоставимых условиях.")
    if len(impressions) == 1 and len(clicks) == 1 and not orders:
        if impressions[0] == 0:
            return source + "при нуле показов доля переходов не определена. Одна проверка: уточни полноту данных за период."
        rate = clicks[0] / impressions[0] * 100
        return source + f"доля переходов — {format_metric_number(rate)}%. По одному периоду динамика и причина неизвестны. Одна проверка: сравни эту долю с предыдущим равным завершённым периодом."
    if len(clicks) == 1 and len(orders) == 1:
        if clicks[0] == 0:
            return source + "при нуле переходов конверсию из них посчитать нельзя. Одна проверка: уточни источник и атрибуцию заказов."
        rate = orders[0] / clicks[0] * 100
        return (source + f"{clicks[0]} переходов и {orders[0]} заказов. "
                f"Если эти заказы относятся именно к этим переходам, доля — {format_metric_number(rate)}%; "
                "для оценки устойчивой конверсии нужны атрибуция и достаточное число наблюдений, а не только итоговые счётчики. "
                "Одна проверка: проверь соответствие карточки обещанию публикации.")
    if len(clicks) == 2:
        if re.search(r"вариант|втрое|лучше|эффектив", text, re.I):
            return ("По числу переходов нельзя установить, какой вариант эффективнее: нужны показы и сопоставимые условия. "
                    "Статистическая значимость не рассчитана. Одна проверка: сравни доли переходов обоих вариантов за сопоставимый период; для этого нужны показы и больше наблюдений.")
        return (source + f"переходы {clicks[0]} → {clicks[1]}. Причина изменения не установлена: "
                "совпадение с частотой публикаций не доказывает причинность. "
                "Одна проверка: сравни показы и долю переходов за равные завершённые периоды.")
    if "posts" in counts and not (impressions or clicks):
        return ("По количеству похожих публикаций нельзя понять, что сработало; результатов по каждой нет. "
                "Одна проверка: сравни доли переходов отдельных публикаций при сопоставимых условиях; "
                "это не устанавливает причину и не доказывает наказание алгоритмом.")
    numerical_kinds = set(counts) - {"constant"}
    if len(numerical_kinds) == 1 and len(counts[next(iter(numerical_kinds))]) == 2:
        kind = next(iter(numerical_kinds))
        before, after = counts[kind]
        change = f"; изменение {format_metric_number((after - before) / before * 100)}%" if before else "; процент изменения от нулевой базы не определён"
        return source + f"{_LABELS[kind].lower()} {before} → {after}{change}. Причина неизвестна; это не оценка эффективности. Одна проверка: уточни, что периоды равны и данные относятся к одному источнику."
    if clicks and not orders and re.search(r"заказ|покуп", text, re.I):
        return None
    return _CLARIFY
