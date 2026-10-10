"""Conservative calculations for counts explicitly supplied by the user.

This is a bounded text parser, not a source of account data. Unclear attribution
is clarified instead of asking a model to guess numbers or causal explanations.
"""
import json
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
_JSON_MAX_LENGTH = 2500


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
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[./]\d{1,2}[./]\d{4}\b", text):
        return None
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
            if re.match(r"\s*(?:год|руб|₽|артикул|процент\w*|%)", clause[number.end():], re.I):
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


_PERIOD_LABEL = re.compile(
    r"(?:(?:за\s+)?(?P<which>прошл\w*|предыдущ\w*|текущ\w*)\s+"
    r"(?P<unit>недел\w*|месяц\w*|период)|(?P<short>раньше|теперь))\s*:", re.I,
)


def _json_metric(key):
    if not isinstance(key, str):
        return None
    key = key.strip().casefold()
    if key in ("impressions", "clicks", "orders", "saves"):
        return key
    if re.fullmatch(
        r"показ(?:ы|ов|а|ах|ами)?|переход(?:ы|ов|а|ах|ами)?|"
        r"(?:исходящ(?:ие|их|ий|его)\s+)?клик(?:и|ов|а|ах|ами)?|"
        r"заказ(?:ы|ов|а|ах|ами)?|покуп(?:ки|ок|ка|ку|ке|ками)?|"
        r"сохранени(?:я|й|е|ю|ям|ях|ями)", key,
    ):
        return _kind(key)
    return None


def _json_period(key):
    if not isinstance(key, str):
        return None
    key = key.strip().casefold()
    if key in ("prev", "previous", "old", "прошлый", "предыдущий", "раньше", "было"):
        return "old", "период"
    if key in ("cur", "current", "new", "текущий", "теперь", "стало"):
        return "new", "период"
    label = _PERIOD_LABEL.fullmatch(key + ":")
    if not label or not re.fullmatch(
        r"(?:за\s+)?(?:прошл(?:ый|ую|ая|ое)|предыдущ(?:ий|ую|ая|ее)|текущ(?:ий|ую|ая|ее))\s+"
        r"(?:недел(?:я|ю|и)|месяц(?:а)?|период)", key,
    ):
        return None
    unit = (label["unit"] or "период").casefold()
    unit = "неделя" if unit.startswith("недел") else "месяц" if unit.startswith("месяц") else "период"
    return ("new" if (label["which"] or label["short"]).startswith(("текущ", "теперь")) else "old"), unit


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _json_format(text):
    """Bounded JSON input -> existing labelled count format, without logging input."""
    if len(text) > _JSON_MAX_LENGTH:
        return None
    fence = re.fullmatch(r"(.*?)```(?:json)?\s*(.*?)```(.*)", text, re.I | re.S)
    if fence:
        prefix, payload, suffix = fence.groups()
    else:
        start = re.search(r"[\[{]", text)
        if not start:
            return None
        prefix, payload, suffix = text[:start.start()], text[start.start():], ""
    # Bound container depth before decoding, ignoring brackets inside strings.
    depth = 0
    quoted = escaped = False
    for char in payload:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 3:
                return None
        elif char in "]}":
            depth -= 1
    try:
        decoder = json.JSONDecoder(
            object_pairs_hook=_json_object, parse_int=Decimal, parse_float=Decimal,
            parse_constant=lambda value: None,
        )
        payload = payload.strip()
        data, end = decoder.raw_decode(payload)
        if end < len(payload) and (fence or not payload[end].isspace()):
            return None
        outside = prefix + " " + payload[end:] + " " + suffix
        if (re.search(r"[{}\[\]`%@]|процент|руб|₽", outside, re.I)
                or _NUMBER.search(outside) or _METRIC.search(outside)
                or re.search(r"\b(?:impressions|clicks|orders|saves)\b", outside, re.I)
                or _EXCLUDE.search(outside)):
            return None
        if isinstance(data, dict) and set(data) in ({"метрики"}, {"metrics"}):
            data = next(iter(data.values()))
        records = []
        if isinstance(data, dict):
            for metric, periods in data.items():
                if not _json_metric(metric) or not isinstance(periods, dict) or len(periods) != 2:
                    return None
                records.extend((metric, period, value) for period, value in periods.items())
        elif isinstance(data, list):
            aliases = {"metric": "metric", "метрика": "metric", "показатель": "metric",
                       "period": "period", "период": "period", "value": "value", "значение": "value"}
            for record in data:
                if not isinstance(record, dict) or len(record) != 3:
                    return None
                fields = {aliases.get(key): value for key, value in record.items()}
                if set(fields) != {"metric", "period", "value"}:
                    return None
                records.append((fields["metric"], fields["period"], fields["value"]))
        else:
            return None
        counts = {}
        units = set()
        for metric, period, raw in records:
            kind, labelled_period = _json_metric(metric), _json_period(period)
            if not kind or not labelled_period:
                return None
            which, unit = labelled_period
            units.add(unit)
            if isinstance(raw, str) and _NUMBER.fullmatch(raw.strip()):
                value = _integer(raw.strip())
            elif isinstance(raw, Decimal) and raw.is_finite() and 0 <= raw <= 10**12 and raw == raw.to_integral_value():
                value = int(raw)
            else:
                return None
            if value is None or which in counts.setdefault(kind, {}):
                return None
            counts[kind][which] = value
        if not counts or len(units) != 1 or any(set(pair) != {"old", "new"} for pair in counts.values()):
            return None
    except (ValueError, InvalidOperation, RecursionError):
        return None
    return "; ".join(
        label + ": " + ", ".join(f"{_LABELS[kind]}: {pair[which]}" for kind, pair in counts.items())
        for which, label in (("old", "Раньше"), ("new", "Теперь"))
    )


def _normalize_format(text):
    """Remove presentation syntax; reorder only complete, explicitly labelled records."""
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"(\d(?:[,.]\d+)?)\s+процент(?:а|ов)?\b", r"\1%", text, flags=re.I)
    text = re.sub(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+", "", text)
    text = re.sub(r"\bтыс\.(?=\s|$)", "тыс", text, flags=re.I)
    for alias, metric in (("impressions", "показы"), ("clicks", "клики"), ("orders", "заказы"), ("saves", "сохранения")):
        text = re.sub(rf"\b{alias}\b", metric, text, flags=re.I)
    # Only a strict three-column table with explicit chronological headers is supported.
    if "|" in text:
        outside = " ".join(line for line in text.splitlines() if "|" not in line)
        if _NUMBER.search(outside) or _METRIC.search(outside) or "@" in outside:
            return None
        rows = [line.strip().strip("|").split("|") for line in text.splitlines() if "|" in line]
        rows = [[cell.strip() for cell in row] for row in rows]
        if not rows or any(len(row) != 3 for row in rows):
            return None
        header = rows.pop(0)
        if header[0].casefold() not in ("метрика", "показатель"):
            return None
        old = [i for i in (1, 2) if re.fullmatch(r"раньше|прошл\w*\s+недел\w*", header[i], re.I)]
        new = [i for i in (1, 2) if re.fullmatch(r"теперь|текущ\w*\s+недел\w*", header[i], re.I)]
        if len(old) != 1 or len(new) != 1 or old == new:
            return None
        records = [[], []]
        for row in rows:
            if all(re.fullmatch(r":?-+:?", cell) for cell in row):
                continue
            if not _METRIC.fullmatch(row[0]) or not all(_NUMBER.fullmatch(row[i]) for i in (1, 2)):
                return None
            for record, column in zip(records, (old[0], new[0])):
                record.append(f"{row[0]}: {row[column]}")
        if not all(records):
            return None
        text = "Раньше: " + ", ".join(records[0]) + "; теперь: " + ", ".join(records[1])
    labels = list(_PERIOD_LABEL.finditer(text))
    if labels:
        if len(labels) != 2:
            return None
        ordered = {}
        units = set()
        for i, label in enumerate(labels):
            which = (label["which"] or label["short"]).casefold()
            key = "new" if which.startswith(("текущ", "теперь")) else "old"
            unit = (label["unit"] or "период").casefold()
            units.add("неделя" if unit.startswith("недел") else "месяц" if unit.startswith("месяц") else unit)
            end = labels[i + 1].start() if i + 1 < len(labels) else len(text)
            body = text[label.end():end].strip(" ;\n")
            counts = _counts(body)
            if key in ordered or not counts or any(len(v) != 1 for v in counts.values()) or "constant" in counts:
                return None
            ordered[key] = (body, set(counts))
        if len(units) != 1 or set(ordered) != {"old", "new"} or ordered["old"][1] != ordered["new"][1]:
            return None
        prefix = text[:labels[0].start()]
        if _NUMBER.search(prefix) or _METRIC.search(prefix):
            return None
        text = prefix + "Раньше: " + ordered["old"][0] + "; теперь: " + ordered["new"][0]
    return text


def _percentage_answer(text):
    """Explicit rate comparison, never an inferred count or a conversion claim."""
    if "%" not in text:
        return None
    if not re.search(r"переход|клик", text, re.I) or re.search(r"показ|заказ|покуп|сохран|публикац|пинов?\b", text, re.I):
        return _CLARIFY
    if not re.search(r"дол[яию]|процент\w*\s+(?:переход|клик)", text, re.I):
        return _CLARIFY
    numbers = list(_NUMBER.finditer(text))
    if len(numbers) != 2 or not all(re.match(r"\s*%", text[m.end():]) for m in numbers):
        return _CLARIFY
    if not re.search(r"был|стал|раньше|теперь|со?\s+\d|→|->", text, re.I):
        return _CLARIFY
    if any(not re.fullmatch(r"[+-]?\d+(?:[,.]\d+)?", m[0]) for m in numbers):
        return _CLARIFY
    values = [Decimal(m[0].replace(",", ".")) for m in numbers]
    if any(v < 0 or v > 100 for v in values):
        return _CLARIFY
    before, after = values
    points = format_metric_number(after - before)
    relative = (f"относительное изменение {format_metric_number((after - before) / before * 100)}%"
                if before else "относительное изменение от нулевой базы не определено")
    return (f"По твоим данным: доля переходов {format_metric_number(before)}% → {format_metric_number(after)}%; "
            f"изменение в процентных пунктах: {points}; {relative}. "
            "Число переходов и заказов из этих процентов неизвестно. Причина неизвестна. "
            "Одна проверка: уточни, что периоды равны и доли рассчитаны одинаково.")


_REFERENCE = re.compile(
    r"(?:сравни|сопоставь)[^.!?]*(?:тем[иу]|этими|прежн|предыдущ|прошл|ранее)[^.!?]*(?:цифр|числ|значени|данн|месяц|недел|период)|"
    r"(?:те|эти|теми|этими|тех|этих)\s+(?:цифр\w*|числ\w*|значени\w*|данн\w*)|"
    r"(?:ранее|выше|раньше)[^.!?]*(?:назван|указан|писал|сообщ|цифр|числ)|"
    r"(?:а\s+)?(?:сейчас|теперь)[^.!?]*\d[^.!?]*(?:вырос|рост|измен|сравни|больше|меньше|упал)|"
    r"на\s+сколько\s+(?:вырос|упал|измен)|"
    r"^\s*а\s+(?:сейчас|теперь)\s+\d", re.I,
)
_HISTORY_PERIOD = re.compile(
    r"\b(?P<which>прошл\w*|предыдущ\w*|текущ\w*|этот|эту|этом|этой)\s+"
    r"(?P<unit>месяц\w*|недел\w*|день|дня|дне)\b|"
    r"\b(?P<now>сейчас|теперь)\b", re.I,
)


def _history_records(text):
    """Accept explicit metric/period records; never infer missing labels."""
    if len(text) > 2500 or _EXCLUDE.search(text):
        return []
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"\bтыс\.(?=\s|$)", "тыс", text, flags=re.I)
    # A separate question about an observation doesn't make its counts a guess.
    clauses = re.split(r"(?<=[.!])\s+", text)
    text = " ".join(clause for clause in clauses if not (
        "?" in clause and not _NUMBER.search(clause) and not _METRIC.search(clause)
        and not _HISTORY_PERIOD.search(clause)
    ))
    # Hypotheses, requests, percentages and multiple sources aren't observations.
    if re.search(r"%|процент|\?|если|допустим|например|не\s+помню|не\s+знаю|артикул|руб|₽|"
                 r"ассистент|ты\s+(?:сказал|писал)|планир|ожида|будет|возможно", text, re.I):
        return []
    profiles = set(re.findall(r"@[a-z0-9._-]+", text.casefold()))
    if len(profiles) > 1 or re.search(r"аккаунт|профил", text, re.I):
        return []
    periods = list(_HISTORY_PERIOD.finditer(text))
    if not periods:
        return []
    records = []
    # Require one period per clause, or explicit leading period labels.
    if len(periods) > 1:
        if not all(re.match(r"\s*:", text[p.end():]) for p in periods):
            return []
        if _NUMBER.search(text[:periods[0].start()]):
            return []
    for i, period in enumerate(periods):
        start = 0 if len(periods) == 1 else period.end() + 1
        end = periods[i + 1].start() if i + 1 < len(periods) else len(text)
        body = text[start:end]
        counts = _counts(body)
        if not counts or "constant" in counts or any(len(v) != 1 for v in counts.values()):
            return []
        # Every count must actually be paired with its metric, not an unrelated ID.
        pairs = list(_PAIR.finditer(body))
        if len(pairs) != len(counts) or len(list(_NUMBER.finditer(body))) != len(pairs):
            return []
        unit = (period["unit"] or "").casefold()
        unit = "месяц" if unit.startswith("месяц") else "неделя" if unit.startswith("недел") else "день" if unit else ""
        which = (period["which"] or "").casefold()
        phase = "old" if which.startswith(("прошл", "предыдущ")) else "new"
        for kind, values in counts.items():
            records.append((kind, unit, phase, values[0], tuple(sorted(profiles))))
    return records


def _history_answer(text, history):
    records = set()
    for message in history:
        if message.get("role", "").casefold() == "user":
            records.update(_history_records(message.get("content", "")))
    metrics = {_kind(m[0]) for m in _METRIC.finditer(text)}
    if metrics:
        records = {r for r in records if r[0] in metrics}
    profiles = tuple(sorted(set(re.findall(r"@[a-z0-9._-]+", text.casefold()))))
    if profiles:
        records = {r for r in records if r[4] == profiles}
    if len(metrics) > 1 or len(profiles) > 1 or re.search(r"аккаунт|профил", text, re.I):
        return _CLARIFY
    if not records or len({r[0] for r in records}) != 1 or len({r[4] for r in records}) != 1:
        return _CLARIFY
    if len({r[1] for r in records}) != 1 or not next(iter(records))[1]:
        return _CLARIFY
    kind, unit, _, _, _ = next(iter(records))
    numbers = list(_NUMBER.finditer(text))
    if numbers:
        # An omitted metric/period is inherited only from a unique labelled base.
        if len(numbers) != 1 or len(records) != 1 or not re.search(r"сейчас|теперь|текущ|этом|этой", text, re.I):
            return _CLARIFY
        before_record = next(iter(records))
        after = _integer(numbers[0][0])
        if after is None or "%" in text or re.search(r"процент|руб|₽|артикул", text, re.I):
            return _CLARIFY
        current_periods = list(_HISTORY_PERIOD.finditer(text))
        for period in current_periods:
            if (period["which"] or "").casefold().startswith(("прошл", "предыдущ")):
                return _CLARIFY
            if period["unit"]:
                word = period["unit"].casefold()
                current_unit = "месяц" if word.startswith("месяц") else "неделя" if word.startswith("недел") else "день"
                if current_unit != unit:
                    return _CLARIFY
        if before_record[2] != "old":
            return _CLARIFY
        before = before_record[3]
    else:
        old = [r for r in records if r[2] == "old"]
        new = [r for r in records if r[2] == "new"]
        if len(old) != 1 or len(new) != 1:
            return _CLARIFY
        before, after = old[0][3], new[0][3]
    change = (f"изменение {format_metric_number((after - before) / before * 100)}%"
              if before else "процент изменения от нулевой базы не определён")
    return (f"По твоим данным: {_LABELS[kind].lower()} {before} → {after}; "
            f"разница {format_metric_number(after - before)}; {change}. "
            "Причина неизвестна. Одна проверка: уточни, что периоды равны, завершены и данные относятся к одному источнику.")


def user_metrics_answer(text, history=()):
    """Answer a supported numeric observation, clarify ambiguity, or return None.

    Only explicitly labelled user observations can be used from history.
    Unsupported non-analytics requests continue through the ordinary chat path.
    """
    if re.search(r"[\[{]|```json\b", text, re.I):
        formatted = _json_format(text)
        if formatted is None:
            return _CLARIFY
        text = formatted
    if len(text) > 2500 or _EXCLUDE.search(text):
        return None
    if _REFERENCE.search(text):
        return _history_answer(text, history)
    if not _METRIC.search(text) and not re.search(r"\b(?:impressions|clicks|orders|saves)\b", text, re.I):
        return None
    if len(set(re.findall(r"@[a-z0-9._-]+", text, re.I))) > 1:
        return "Для какого одного профиля разбираем цифры? Укажи его и числа за два сравнимых периода."
    profile_labels = re.findall(r"(?:перв\w*|втор\w*)\s+(?:(?:pinterest|пинтерест)[ -]*)?(?:аккаунт|профил)", text, re.I)
    if len(profile_labels) > 1 or (profile_labels and re.search(r"во?\s+втор\w*\s+\d", text, re.I)):
        return "Для какого одного профиля разбираем цифры? Укажи его и числа за два сравнимых периода."
    formatted = _normalize_format(text)
    if formatted is None:
        return _CLARIFY
    text = formatted
    if not _METRIC.search(text):
        return None
    if re.search(r"вчера", text, re.I) and re.search(r"почему", text, re.I):
        return None
    if re.match(r"\s*Цена\b", text, re.I):
        return None
    if not _NUMBER.search(text) or not re.search(
        r"→|->|доля|был|стало|упал|вырос|сниз|удво|не\s+измен|выложил|вариант|получается|вывод|значит|сработ|эффектив|причин|что\s+проверить|это\s+хорош|бесполез|изменил|почему|конверт|неделя:|раньше|теперь|(?:показы|переходы|клики|заказы)\s*[:=]\s*\d", text, re.I,
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
    percentage = _percentage_answer(text)
    if percentage is not None:
        return percentage
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
        if not re.search(r"со?\s+\d|до\s+\d|был|стал|прошл|текущ|раньше|теперь|→|->", text, re.I):
            return _CLARIFY
        return (source + f"переходы {clicks[0]} → {clicks[1]}. Причина изменения не установлена: "
                "совпадение с частотой публикаций не доказывает причинность. "
                "Одна проверка: сравни показы и долю переходов за равные завершённые периоды.")
    if "posts" in counts and not (impressions or clicks):
        return ("По количеству похожих публикаций нельзя понять, что сработало; результатов по каждой нет. "
                "Одна проверка: сравни доли переходов отдельных публикаций при сопоставимых условиях; "
                "это не устанавливает причину и не доказывает наказание алгоритмом.")
    numerical_kinds = set(counts) - {"constant"}
    if len(numerical_kinds) == 1 and len(counts[next(iter(numerical_kinds))]) == 2:
        if not re.search(r"со?\s+\d|до\s+\d|был|стал|прошл|текущ|раньше|теперь|→|->", text, re.I):
            return _CLARIFY
        kind = next(iter(numerical_kinds))
        before, after = counts[kind]
        change = f"; изменение {format_metric_number((after - before) / before * 100)}%" if before else "; процент изменения от нулевой базы не определён"
        return source + f"{_LABELS[kind].lower()} {before} → {after}{change}. Причина неизвестна; это не оценка эффективности. Одна проверка: уточни, что периоды равны и данные относятся к одному источнику."
    if clicks and not orders and re.search(r"заказ|покуп", text, re.I):
        return None
    return _CLARIFY
