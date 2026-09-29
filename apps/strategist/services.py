import json
import logging
import math
import re
from datetime import date, timedelta

from django.utils import timezone
from django.utils.text import slugify

from apps.businesses.models import Business
from apps.knowledge.services import format_knowledge_context, search_knowledge
from apps.pinterest.models import PinterestAccount
from apps.pinterest.strategist_tools import pinterest_read_function, read_pinterest_data
from apps.pinterest.sync import fresh_snapshot_resource, sync_pinterest_account

from .models import AIConversation, AIMessage
from .prompts import build_strategist_system_prompt
from .providers import GigaChatCompletion, GigaChatProvider

logger = logging.getLogger(__name__)

ORGANIC_METRIC_LABELS = {
    "IMPRESSION": "Показы",
    "ENGAGEMENT": "Взаимодействия",
    "PIN_CLICK": "Открытия пина",
    "OUTBOUND_CLICK": "Исходящие клики",
    "SAVE": "Сохранения",
    "VIDEO_START": "Запуски видео",
    "VIDEO_MRC_VIEW": "Просмотры видео от 2 секунд",
    "VIDEO_10S_VIEW": "Просмотры видео от 10 секунд",
    "QUARTILE_95_PERCENT_VIEW": "Просмотры видео до 95%",
}


def _asks_for_pinterest_account_list(message: str) -> bool:
    normalized = message.casefold()
    asks_for_list = re.search(r"\b(какие|сколько|список|перечисли|покажи|назови)\w*\b", normalized)
    mentions_account = re.search(r"\b(аккаунт|профил|пинтерест|pinterest)\w*\b", normalized)
    return bool(asks_for_list and mentions_account)


def _pinterest_account_list_answer(accounts: list[PinterestAccount]) -> str:
    connected = [account for account in accounts if account.status == PinterestAccount.Status.CONNECTED]
    reauth_required = [
        account for account in accounts if account.status == PinterestAccount.Status.REAUTH_REQUIRED
    ]
    lines = []
    if connected:
        lines.append(f"Подключённые Pinterest-профили ({len(connected)}):")
        lines.extend(f"• @{account.username or 'без имени'}" for account in connected)
    else:
        lines.append("Сейчас подключённых Pinterest-профилей нет.")
    if reauth_required:
        lines.append("Требуют переподключения:")
        lines.extend(f"• @{account.username or 'без имени'}" for account in reauth_required)
    return "\n".join(lines)


def _account_for_pinterest_request(message: str, accounts: list[PinterestAccount]) -> PinterestAccount | None:
    requested_username = re.search(r"@([A-Za-z0-9._-]{1,100})", message)
    connected = [account for account in accounts if account.status == PinterestAccount.Status.CONNECTED]
    if requested_username:
        username = requested_username.group(1).casefold()
        return next((account for account in connected if account.username.casefold() == username), None)
    return connected[0] if len(connected) == 1 else None


def _read_pinterest_resource(*, business: Business, account: PinterestAccount, resource: str, options: dict | None = None):
    return read_pinterest_data(
        business=business,
        arguments={
            "account_key": str(account.public_id),
            "resource": resource,
            "options": json.dumps(options or {}, ensure_ascii=False),
            "page_size": 250,
        },
    )


def _read_all_pinterest_pages(*, business: Business, account: PinterestAccount, resource: str):
    items = []
    bookmark = None
    for _ in range(4):
        arguments = {
            "account_key": str(account.public_id),
            "resource": resource,
            "options": "{}",
            "page_size": 250,
        }
        if bookmark:
            arguments["bookmark"] = bookmark
        response = read_pinterest_data(business=business, arguments=arguments)
        if response.get("error"):
            return response
        page_items = response.get("items")
        if not isinstance(page_items, list):
            return {"error": "Pinterest API вернул ответ без списка записей."}
        items.extend(page_items)
        bookmark = response.get("bookmark")
        if not bookmark:
            return {"items": items}
    return {"items": items, "truncated": True}


def _pinterest_board_answer(*, business: Business, account: PinterestAccount) -> str:
    snapshot = fresh_snapshot_resource(account=account, resource="boards")
    if snapshot and snapshot.get("complete"):
        boards = snapshot.get("items", [])
        names = [board.get("name") for board in boards if isinstance(board, dict) and board.get("name")]
        synced_at = snapshot.get("synced_at", "")[:16].replace("T", " ")
        lines = [f"В синхронизированных данных Pinterest ({synced_at}) — {len(boards)} досок @{account.username}:"]
        lines.extend(f"• {name}" for name in names)
        return "\n".join(lines)
    response = _read_all_pinterest_pages(business=business, account=account, resource="boards")
    if response.get("error"):
        return f"Не удалось прочитать доски @{account.username}: {response['error']}"
    boards = response["items"]
    names = [board.get("name") for board in boards if isinstance(board, dict) and board.get("name")]
    lines = [f"Pinterest API вернул {len(boards)} досок для @{account.username}:"]
    lines.extend(f"• {name}" for name in names)
    if response.get("truncated"):
        lines.append("Список неполный: достигнут предел чтения страниц за один запрос.")
    return "\n".join(lines)


def _parse_pinterest_period(message: str) -> tuple[date, date] | None:
    today = timezone.now().date()
    exact_dates = re.search(
        r"(\d{4}-\d{2}-\d{2})\s*(?:—|–|\bпо\b|\bдо\b)\s*(\d{4}-\d{2}-\d{2})",
        message,
        re.IGNORECASE,
    )
    if exact_dates:
        try:
            return date.fromisoformat(exact_dates.group(1)), date.fromisoformat(exact_dates.group(2))
        except ValueError:
            return None

    normalized = message.casefold()
    days_match = re.search(r"(?:за\s+)?(?:последние\s+)?(\d{1,3})\s*(?:дн(?:я|ей|и)?|сут(?:ки|ок)?)", normalized)
    if days_match:
        days = int(days_match.group(1))
    elif re.search(r"за\s+(?:последн\w+\s+)?недел\w*", normalized):
        days = 7
    elif re.search(r"за\s+(?:последн\w+\s+)?месяц\w*", normalized):
        days = 30
    elif re.search(r"за\s+(?:последн\w+\s+)?(?:квартал\w*|3\s+месяц\w*)", normalized):
        days = 90
    else:
        return None
    if not 1 <= days <= 90:
        return None
    return today - timedelta(days=days - 1), today


def _pinterest_period_error(start_date: date, end_date: date) -> str | None:
    today = timezone.now().date()
    if start_date > end_date:
        return "Начальная дата должна быть раньше конечной."
    if end_date > today:
        return "Pinterest принимает даты статистики по UTC не позднее сегодняшней даты."
    if start_date < today - timedelta(days=90) or (end_date - start_date).days > 90:
        return "Pinterest отдаёт органическую статистику только в пределах 90-дневного окна. Укажи даты не старше последних 90 дней."
    return None


def _analytics_summary(result: dict) -> dict:
    summary = {}
    for group in result.values():
        if isinstance(group, dict) and isinstance(group.get("summary_metrics"), dict):
            summary.update(group["summary_metrics"])
    return summary


def _metric_value(summary: dict, name: str) -> int | float | None:
    value = summary.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _format_metric_number(value: int | float) -> str:
    return str(int(value)) if value == int(value) else f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _format_pinterest_analytics(
    *, account: PinterestAccount, result: dict, start_date: date, end_date: date,
    previous_result: dict | None = None, previous_period: tuple[date, date] | None = None,
    synced_at: str = "",
) -> str:
    groups = [
        value for value in result.values()
        if isinstance(value, dict) and ("summary_metrics" in value or "daily_metrics" in value)
    ]
    if not groups:
        return "Pinterest API вернул статистику в неподдерживаемом формате; значения не интерпретированы."
    summary = _analytics_summary(result)
    main_metrics = ("IMPRESSION", "PIN_CLICK", "SAVE", "OUTBOUND_CLICK")
    if not any(_metric_value(summary, name) is not None for name in main_metrics):
        return f"Pinterest API не вернул основные показатели для @{account.username} за выбранный период."

    lines = [f"Органика @{account.username} · {start_date} — {end_date} (Pinterest API)" + (f"; синхронизация {synced_at}" if synced_at else "")]
    rates = {"PIN_CLICK": "PIN_CLICK_RATE", "SAVE": "SAVE_RATE"}
    overview = []
    for name in main_metrics:
        value = _metric_value(summary, name)
        if value is None:
            continue
        item = f"{ORGANIC_METRIC_LABELS[name].lower()} — {_format_metric_number(value)}"
        rate = _metric_value(summary, rates.get(name, ""))
        if rate is not None:
            item += f" ({_format_metric_number(rate * 100)}%)"
        overview.append(item)
    lines.append("За период: " + "; ".join(overview) + ".")

    video_metrics = ("VIDEO_START", "VIDEO_MRC_VIEW", "VIDEO_10S_VIEW", "QUARTILE_95_PERCENT_VIEW")
    video = [
        f"{ORGANIC_METRIC_LABELS[name].lower()} — {_format_metric_number(value)}"
        for name in video_metrics
        if (value := _metric_value(summary, name)) is not None
    ]
    if video:
        lines.append("Видео: " + "; ".join(video) + ".")

    if previous_period:
        previous = _analytics_summary(previous_result) if previous_result else {}
        comparison = []
        for name in main_metrics:
            current_value = _metric_value(summary, name)
            previous_value = _metric_value(previous, name)
            if current_value is None or previous_value is None:
                continue
            change = current_value - previous_value
            change_text = f"{_format_metric_number(previous_value)} → {_format_metric_number(current_value)}"
            if change:
                delta = f"{'+' if change > 0 else ''}{_format_metric_number(change)}"
                if name == "IMPRESSION" and previous_value:
                    delta += f"; {change / previous_value * 100:+.1f}%".replace(".", ",")
                change_text += f" ({delta})"
            comparison.append(f"{ORGANIC_METRIC_LABELS[name].lower()} {change_text}")
        if comparison:
            lines.append(f"К предыдущему периоду {previous_period[0]} — {previous_period[1]}: " + "; ".join(comparison) + ".")
        else:
            lines.append("Сравнение с предыдущим равным периодом недоступно.")

    excluded_dates = set()
    estimated_dates = set()
    impression_days = []
    for group in groups:
        for row in group.get("daily_metrics", []) if isinstance(group.get("daily_metrics"), list) else []:
            if not isinstance(row, dict):
                continue
            day = row.get("date")
            status = row.get("data_status")
            status = status.get("value") if isinstance(status, dict) else status
            if status not in (None, "READY", "ESTIMATE"):
                if day:
                    excluded_dates.add(str(day))
                continue
            if status == "ESTIMATE" and day:
                estimated_dates.add(str(day))
            metrics = row.get("metrics")
            impressions = _metric_value(metrics, "IMPRESSION") if isinstance(metrics, dict) else None
            if impressions is not None and day:
                impression_days.append((impressions, str(day)))
    if impression_days:
        value, day = max(impression_days)
        lines.append(f"Максимум показов среди доступных дней: {_format_metric_number(value)} ({day}).")
    if _metric_value(summary, "PIN_CLICK") and _metric_value(summary, "OUTBOUND_CLICK") == 0:
        lines.append("Пины открывали, но Pinterest не зафиксировал исходящих кликов. Причину эти данные не показывают.")
    if excluded_dates or estimated_dates:
        lines.append(f"Ограничение данных: недоступных дат — {len(excluded_dates)}, предварительных — {len(estimated_dates)}.")
    if end_date == timezone.now().date():
        lines.append("Последний день периода по UTC ещё может быть неполным.")
    return "\n".join(lines)


def _pinterest_analytics_answer(*, business: Business, account: PinterestAccount, start_date: date, end_date: date) -> str:
    period_error = _pinterest_period_error(start_date, end_date)
    if period_error:
        return period_error
    snapshot = fresh_snapshot_resource(account=account, resource="analytics")
    result = None
    synced_at = ""
    if snapshot:
        cached_response = snapshot.get("response", {})
        cached_period = cached_response.get("period", {})
        if cached_period.get("start_date") == start_date.isoformat() and cached_period.get("end_date") == end_date.isoformat():
            synced_at = snapshot.get("synced_at", "")[:16].replace("T", " ")
            result = cached_response
    if result is None:
        result = _read_pinterest_resource(
            business=business,
            account=account,
            resource="analytics",
            options={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "content_type": "ORGANIC",
            },
        )
    if not isinstance(result, dict):
        return "Pinterest API вернул статистику в неподдерживаемом формате; значения не интерпретированы."
    if result.get("error"):
        return f"Не удалось получить статистику @{account.username}: {result['error']}"

    previous_period = None
    previous_result = None
    period_days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    if _pinterest_period_error(previous_start, previous_end) is None:
        previous_period = (previous_start, previous_end)
        previous_result = _read_pinterest_resource(
            business=business,
            account=account,
            resource="analytics",
            options={
                "start_date": previous_start.isoformat(),
                "end_date": previous_end.isoformat(),
                "content_type": "ORGANIC",
            },
        )
        if not isinstance(previous_result, dict) or previous_result.get("error"):
            previous_result = None
    return _format_pinterest_analytics(
        account=account,
        result=result,
        start_date=start_date,
        end_date=end_date,
        previous_result=previous_result,
        previous_period=previous_period,
        synced_at=synced_at,
    )


def _direct_pinterest_answer(*, user_message: AIMessage, accounts: list[PinterestAccount]) -> AIMessage | None:
    effective_message = user_message
    period = _parse_pinterest_period(user_message.content)
    previous_assistant = user_message.conversation.messages.filter(
        role=AIMessage.Role.ASSISTANT,
        created_at__lt=user_message.created_at,
    ).order_by("-created_at").first()
    previous_message_requested_period = bool(
        previous_assistant
        and (
            previous_assistant.model == "pinterest-period-selection"
            or "Выбери период:" in previous_assistant.content
        )
    )
    if previous_message_requested_period:
        short_period_choice = re.fullmatch(r"\s*(7|30|90)\s*", user_message.content.strip())
        if short_period_choice:
            days = int(short_period_choice.group(1))
            today = timezone.now().date()
            period = (today - timedelta(days=days - 1), today)
        if period:
            effective_message = user_message.conversation.messages.filter(
                role=AIMessage.Role.USER,
                created_at__lt=previous_assistant.created_at,
            ).order_by("-created_at").first() or user_message
    normalized = effective_message.content.casefold()
    is_sync_request = (
        any(word in normalized for word in ("синхронизац", "синхронизируй", "синхронизировать", "обнови данные", "обновить данные"))
        and (
            "pinterest" in normalized
            or "пинтерест" in normalized
            or re.search(r"@[A-Za-z0-9._-]{1,100}", user_message.content)
            or any(word in normalized for word in ("аккаунт", "профил", "доск", "пин"))
        )
    )
    if is_sync_request:
        account = _account_for_pinterest_request(user_message.content, accounts)
        if account is None:
            connected = [item for item in accounts if item.status == PinterestAccount.Status.CONNECTED]
            answer = (
                "У этого бизнеса нет подключённых Pinterest-профилей для синхронизации."
                if not connected
                else "Уточни профиль для синхронизации: " + ", ".join(f"@{item.username}" for item in connected) + "."
            )
        else:
            result = sync_pinterest_account(account=account)
            if result.get("busy"):
                answer = f"Синхронизация @{account.username} уже выполняется."
            elif result.get("synced"):
                completed = [name for name, state in result["resources"].items() if state.get("ok")]
                failed = [name for name, state in result["resources"].items() if state.get("error")]
                answer = f"С Pinterest синхронизированы данные @{account.username}: {', '.join(completed)}."
                if failed:
                    answer += f" Не удалось обновить: {', '.join(failed)}."
                if any(not state.get("complete", True) for state in result["resources"].values() if state.get("ok")):
                    answer += " Список досок неполный: достигнут лимит страниц синхронизации."
            else:
                answer = f"Pinterest не вернул данные для синхронизации @{account.username}. Проверь разрешения аккаунта."
        return AIMessage.objects.create(
            conversation=user_message.conversation,
            role=AIMessage.Role.ASSISTANT,
            content=answer,
            provider="pinterest-api",
            model="explicit-sync",
        )

    mentions_pinterest_account = bool(
        any(word in normalized for word in ("pinterest", "пинтерест", "аккаунт", "профил", "доск", "пин"))
        or re.search(r"@[A-Za-z0-9._-]{1,100}", effective_message.content)
    )
    is_analytics_question = mentions_pinterest_account and any(
        word in normalized
        for word in (
            "статист",
            "аналитик",
            "анализ",
            "показател",
            "динамик",
            "произошл",
            "изменил",
            "вырос",
            "упал",
            "снизил",
            "пик",
            "минимум",
        )
    )
    is_board_question = not is_analytics_question and ("доск" in normalized or "board" in normalized)
    if not is_board_question and not is_analytics_question:
        return None
    account = _account_for_pinterest_request(effective_message.content, accounts)
    if account is None:
        connected = [item for item in accounts if item.status == PinterestAccount.Status.CONNECTED]
        requested_username = re.search(r"@([A-Za-z0-9._-]{1,100})", effective_message.content)
        reauth_account = next(
            (
                item for item in accounts
                if requested_username
                and item.username.casefold() == requested_username.group(1).casefold()
                and item.status == PinterestAccount.Status.REAUTH_REQUIRED
            ),
            None,
        )
        if reauth_account:
            answer = f"Профиль @{reauth_account.username} требует переподключения в настройках бизнеса."
        elif not connected:
            answer = "У этого бизнеса нет подключённых Pinterest-профилей для запроса."
        elif requested_username:
            answer = "Профиль с таким именем не подключён к этому бизнесу. Выбери профиль из списка подключённых."
        else:
            names = ", ".join(f"@{item.username}" for item in connected)
            answer = f"Уточни профиль: {names}."
        content = answer
    elif is_board_question:
        content = _pinterest_board_answer(business=user_message.conversation.business, account=account)
    else:
        if period is None:
            content = (
                "Pinterest отдаёт органическую статистику только в пределах последних 90 дней. "
                "Выбери период: за 7, 30 или 90 дней либо укажи даты в формате YYYY-MM-DD — YYYY-MM-DD."
            )
            return AIMessage.objects.create(
                conversation=user_message.conversation,
                role=AIMessage.Role.ASSISTANT,
                content=content,
                provider="pinterest-api",
                model="pinterest-period-selection",
            )
        content = _pinterest_analytics_answer(
            business=user_message.conversation.business,
            account=account,
            start_date=period[0],
            end_date=period[1],
        )
    return AIMessage.objects.create(
        conversation=user_message.conversation,
        role=AIMessage.Role.ASSISTANT,
        content=content,
        provider="pinterest-api",
        model="direct-read",
    )


def create_conversation(*, business: Business, user) -> AIConversation:
    conversation = AIConversation.objects.create(business=business, created_by=user)
    conversation.slug = f"session-{conversation.public_id.hex[:8]}"
    conversation.save(update_fields=["slug"])
    return conversation


def conversation_slug(*, title: str, conversation: AIConversation) -> str:
    base_slug = slugify(title)[:180].rstrip("-") or "session"
    return f"{base_slug}-{conversation.public_id.hex[:8]}"


def respond_to_message(*, user_message: AIMessage) -> AIMessage:
    conversation = user_message.conversation
    pinterest_accounts = list(
        PinterestAccount.objects.filter(
            business=conversation.business,
            deleted_at__isnull=True,
        ).order_by("created_at")
    )
    direct_pinterest_answer = _direct_pinterest_answer(
        user_message=user_message,
        accounts=pinterest_accounts,
    )
    if direct_pinterest_answer:
        return direct_pinterest_answer
    if _asks_for_pinterest_account_list(user_message.content):
        return AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.ASSISTANT,
            content=_pinterest_account_list_answer(pinterest_accounts),
            provider="database",
            model="pinterest-account-inventory",
        )

    history = list(
        conversation.messages.order_by("-created_at").values("role", "content")[:12]
    )
    history.reverse()
    provider = GigaChatProvider()
    pinterest_context = [
        {
            "account_key": str(account.public_id),
            "username": account.username,
            "status": account.get_status_display(),
            "scopes": sorted(set(account.granted_scopes or [])),
        }
        for account in pinterest_accounts
    ]
    try:
        knowledge_hits = search_knowledge(query=user_message.content, embedder=provider)
    except Exception as error:
        logger.warning("Knowledge retrieval failed; continuing without RAG: %s", type(error).__name__)
        knowledge_hits = []

    messages = [
        {
            "role": "system",
            "content": build_strategist_system_prompt(
                conversation.business,
                knowledge_context=format_knowledge_context(knowledge_hits),
                pinterest_accounts=pinterest_context,
            ),
        },
        *[
            {"role": "user" if item["role"] == AIMessage.Role.USER else "assistant", "content": item["content"]}
            for item in history
        ],
    ]
    asks_for_pinterest_data = bool(
        re.search(
            r"pinterest|пинтерест|аккаунт|профил|доск|пин|аналитик|статист|подписчик|просмотр|тренд",
            user_message.content,
            re.IGNORECASE,
        )
        or re.search(r"@[A-Za-z0-9._-]{1,100}", user_message.content)
    )
    functions = (
        [pinterest_read_function()]
        if asks_for_pinterest_data
        and any(account.status == PinterestAccount.Status.CONNECTED for account in pinterest_accounts)
        else None
    )
    completion: GigaChatCompletion | None = None
    prompt_tokens = completion_tokens = total_tokens = 0
    for _ in range(6):
        completion = provider.complete(
            messages,
            functions=functions,
            function_call="auto" if functions else None,
        )
        prompt_tokens += completion.prompt_tokens
        completion_tokens += completion.completion_tokens
        total_tokens += completion.total_tokens
        if not completion.function_call:
            break
        call = completion.function_call
        messages.append(
            {
                "role": "assistant",
                "content": completion.content,
                "function_call": call,
                "functions_state_id": completion.functions_state_id,
            }
        )
        try:
            arguments = call.get("arguments") or {}
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise ValueError("Invalid function arguments")
            if call.get("name") == "read_pinterest_data":
                result = read_pinterest_data(
                    business=conversation.business,
                    arguments=arguments,
                )
            else:
                result = {"error": "Эта функция недоступна."}
        except (TypeError, ValueError, json.JSONDecodeError):
            result = {"error": "Не удалось разобрать параметры чтения Pinterest API."}
        except Exception as error:
            logger.warning("Pinterest strategist read failed: %s", type(error).__name__)
            result = {"error": "Не удалось прочитать Pinterest API."}
        if result.get("error"):
            return AIMessage.objects.create(
                conversation=conversation,
                role=AIMessage.Role.ASSISTANT,
                content=f"Не удалось получить данные Pinterest: {result['error']} Не буду делать выводы без ответа API.",
                provider="pinterest-api",
                model="read-error",
            )
        messages.append(
            {
                "role": "function",
                "name": call.get("name", "read_pinterest_data"),
                "content": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            }
        )
    else:
        messages.append(
            {
                "role": "user",
                "content": "Достигнут лимит чтения Pinterest API в этом ответе. "
                "Не делай выводов по не загруженным данным и явно обозначь, если анализ неполный.",
            }
        )
        completion = provider.complete(messages, function_call="none")
        prompt_tokens += completion.prompt_tokens
        completion_tokens += completion.completion_tokens
        total_tokens += completion.total_tokens
    if completion is None or completion.function_call:
        completion = provider.complete(messages, function_call="none")
        prompt_tokens += completion.prompt_tokens
        completion_tokens += completion.completion_tokens
        total_tokens += completion.total_tokens
    return AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.ASSISTANT,
        content=completion.content,
        provider="gigachat",
        model=completion.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
