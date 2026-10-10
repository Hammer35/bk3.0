"""Read-only Pinterest API tools exposed to the business strategist."""

import json
import re
import uuid
from datetime import date, timedelta
from urllib.parse import quote

import requests
from django.utils import timezone
from gigachat.models import Function, FunctionParameters
from gigachat.models.function_parameters_property import FunctionParametersProperty

from .crypto import decrypt_token
from .models import PinterestAccount
from .services import API_URL, refresh_account_token


class PinterestReadError(Exception):
    pass


_RESOURCES = {
    "profile": ("/user_account", {"user_accounts:read"}),
    "linked_businesses": ("/user_account/businesses", {"user_accounts:read"}),
    "followers": ("/user_account/followers", {"user_accounts:read"}),
    "following": ("/user_account/following", {"user_accounts:read"}),
    "following_boards": ("/user_account/following/boards", {"user_accounts:read"}),
    "websites": ("/user_account/websites", {"user_accounts:read"}),
    "website_verification": ("/user_account/websites/verification", {"user_accounts:read"}),
    "boards": ("/boards", {"boards:read"}),
    "secret_boards": ("/search/boards", {"boards:read", "boards:read_secret"}),
    "board": ("/boards/{board_id}", {"boards:read"}),
    "pins": ("/pins", {"boards:read", "pins:read"}),
    "search_pins": ("/search/pins", {"boards:read", "boards:read_secret", "pins:read", "pins:read_secret"}),
    "partner_pins": ("/search/partner/pins", {"boards:read", "pins:read"}),
    "pin": ("/pins/{pin_id}", {"boards:read", "pins:read"}),
    "pin_tags": ("/pins/{pin_id}/product_tags", {"boards:read", "pins:read"}),
    "sections": ("/boards/{board_id}/sections", {"boards:read"}),
    "board_pins": ("/boards/{board_id}/pins", {"boards:read", "pins:read"}),
    "section_pins": ("/boards/{board_id}/sections/{section_id}/pins", {"boards:read", "pins:read"}),
    "media": ("/media", {"pins:read"}),
    "media_item": ("/media/{media_id}", {"pins:read"}),
    "analytics": ("/user_account/analytics", {"user_accounts:read"}),
    "delivery_metrics": ("/resources/delivery_metrics", {"user_accounts:read"}),
    "top_pins": ("/user_account/analytics/top_pins", {"user_accounts:read", "pins:read"}),
    "top_video_pins": ("/user_account/analytics/top_video_pins", {"user_accounts:read", "pins:read"}),
    "pin_analytics": ("/pins/{pin_id}/analytics", {"boards:read", "pins:read"}),
    "pins_analytics": ("/pins/analytics", {"boards:read", "pins:read"}),
    "followed_interests": ("/users/{username}/interests/follow", {"user_accounts:read"}),
    "trend_articles": ("/trends/editorial_articles", {"user_accounts:read"}),
    "trend_keywords": ("/trends/keywords/{region}/top/{trend_type}", {"user_accounts:read"}),
    "suggested_terms": ("/terms/suggested", {"ads:read"}),
    "related_terms": ("/terms/related", {"ads:read"}),
    "trend_category_details": ("/trends/product_categories/details", {"user_accounts:read"}),
    "trend_categories": ("/trends/product_categories/trending", {"user_accounts:read"}),
    "trend_topics": ("/trends/topics/featured", {"user_accounts:read"}),
}

_PAGINATED = {
    "followers", "following", "following_boards", "websites", "boards", "secret_boards",
    "pins", "sections", "board_pins", "section_pins",
    "media", "followed_interests",
}
_OPTION_KEYS = {
    "following": {"explicit_following", "feed_type"},
    "following_boards": {"explicit_following"},
    "boards": {"privacy"},
    "secret_boards": {"query"},
    "pins": {"pin_metrics", "include_protected_pins", "pin_type", "creative_types", "domain", "domains", "include_product_tag_obj"},
    "search_pins": {"query"},
    "partner_pins": {"term", "country_code", "locale", "limit"},
    "board_pins": {"pin_metrics", "creative_types"},
    "section_pins": {"creative_types"},
    "pin": {"pin_metrics"},
    "analytics": {"start_date", "end_date", "from_claimed_content", "pin_format", "app_types", "content_type", "source", "metric_types", "split_field"},
    "delivery_metrics": {"report_type"},
    "top_pins": {"start_date", "end_date", "sort_by", "from_claimed_content", "pin_format", "app_types", "content_type", "source", "metric_types", "num_of_pins", "created_in_last_n_days"},
    "top_video_pins": {"start_date", "end_date", "sort_by", "from_claimed_content", "pin_format", "app_types", "content_type", "source", "metric_types", "num_of_pins", "created_in_last_n_days"},
    "pin_analytics": {"start_date", "end_date", "app_types", "metric_types", "split_field"},
    "pins_analytics": {"pin_ids", "start_date", "end_date", "app_types", "metric_types"},
    "trend_articles": {"region"},
    "trend_keywords": {"interests", "genders", "ages", "include_keywords", "normalize_against_group", "limit", "include_demographics"},
    "suggested_terms": {"term", "limit"},
    "related_terms": {"terms"},
    "trend_category_details": {"product_categories", "region", "lookback_window", "engagement_type"},
    "trend_categories": {"region", "verticals", "ages", "genders", "engagement_type"},
    "trend_topics": {"interest", "region"},
}
_REQUIRED_OPTIONS = {
    "secret_boards": {"query"}, "search_pins": {"query"},
    "partner_pins": {"term", "country_code"},
    "analytics": {"start_date", "end_date"},
    "delivery_metrics": {"report_type"},
    "top_pins": {"start_date", "end_date", "sort_by"},
    "top_video_pins": {"start_date", "end_date", "sort_by"},
    "pin_analytics": {"start_date", "end_date", "metric_types"},
    "pins_analytics": {"pin_ids", "start_date", "end_date", "metric_types"},
    "trend_articles": {"region"},
    "suggested_terms": {"term"}, "related_terms": {"terms"},
    "trend_category_details": {"product_categories", "region"},
    "trend_categories": {"region"}, "trend_topics": {"region"},
}


def pinterest_read_function():
    return Function(
        name="read_pinterest_data",
        description=(
            "Читает один документированный Pinterest API v5 GET ресурс для аккаунта текущего бизнеса. "
            "Доступные resource: " + ", ".join(_RESOURCES) + ". Функция только читает. "
            "Для endpoint-specific параметров передавай options как JSON-строку; используй только "
            "параметры, указанные для выбранного ресурса: secret_boards(query), search_pins(query), "
            "partner_pins(term,country_code,locale,limit), analytics(start_date,end_date,metric_types и "
            "фильтры аналитики), delivery_metrics(report_type=SYNC для списка метрик), "
            "top_pins/top_video_pins(start_date,end_date,sort_by,num_of_pins,content_type,metric_types), "
            "Для top_pins количество результатов задаётся options.num_of_pins (1–50), "
            "не limit и не page_size. Для топа по исходящим кликам: sort_by=OUTBOUND_CLICK, "
            "content_type=ORGANIC, num_of_pins=5; даты бери из запроса пользователя. "
            "Для исходящих кликов код метрики OUTBOUND_CLICK (единственное число); "
            "metric_types можно не передавать: API по умолчанию возвращает все метрики. "
            "pin_analytics(pin_id,start_date,end_date,metric_types), pins_analytics(pin_ids,start_date, "
            "end_date,metric_types), trend_articles(region), trend_keywords(region,trend_type path arguments), "
            "suggested_terms(term,limit), related_terms(terms), "
            "trend_category_details(product_categories,region), trend_categories(region), "
            "trend_topics(region). Массивы кодируй JSON-массивами. Передавай bookmark из ответа "
            "без изменений для следующей страницы."
        ),
        parameters=FunctionParameters(
            type="object",
            properties={
                "account_key": FunctionParametersProperty(type="string", description="Ключ аккаунта из контекста текущего бизнеса."),
                "resource": FunctionParametersProperty(type="string", enum=list(_RESOURCES)),
                "board_id": FunctionParametersProperty(type="string", description="ID доски из Pinterest API."),
                "section_id": FunctionParametersProperty(type="string", description="ID раздела из Pinterest API."),
                "pin_id": FunctionParametersProperty(type="string", description="ID Pin из Pinterest API."),
                "media_id": FunctionParametersProperty(type="string", description="ID media из Pinterest API."),
                "username": FunctionParametersProperty(type="string", description="Имя аккаунта для followed_interests."),
                "region": FunctionParametersProperty(type="string", description="Документированный Pinterest region."),
                "trend_type": FunctionParametersProperty(type="string", description="Документированный Pinterest trend_type."),
                "bookmark": FunctionParametersProperty(type="string", description="bookmark из предыдущей страницы Pinterest."),
                "page_size": FunctionParametersProperty(type="integer", description="Размер страницы от 1 до 250."),
                "options": FunctionParametersProperty(type="string", description="JSON-строка с параметрами из описания выбранного resource."),
            },
            required=["account_key", "resource"],
        ),
    )


def read_pinterest_data(*, business, arguments):
    try:
        account_key = uuid.UUID(str(arguments.get("account_key", "")))
    except (TypeError, ValueError):
        return {"error": "Укажи account_key из списка текущего бизнеса."}
    account = PinterestAccount.objects.filter(
        public_id=account_key,
        business=business,
        deleted_at__isnull=True,
        status=PinterestAccount.Status.CONNECTED,
    ).first()
    if not account:
        return {"error": "Аккаунт не подключён к текущему бизнесу или требует переподключения."}

    resource = arguments.get("resource")
    raw_options = arguments.get("options") or "{}"
    try:
        options = json.loads(raw_options) if isinstance(raw_options, str) else raw_options
    except (TypeError, json.JSONDecodeError):
        return {"error": "options должен быть JSON-объектом документированных параметров."}
    if not isinstance(options, dict):
        return {"error": "options должен быть JSON-объектом документированных параметров."}
    endpoint = _endpoint(resource, arguments, options)
    if isinstance(endpoint, dict):
        return endpoint
    path, params, required_scopes = endpoint
    scopes = set(account.granted_scopes or [])
    missing_scopes = required_scopes - scopes
    if missing_scopes:
        return {"error": "У этого Pinterest аккаунта нет нужных разрешений.", "required_scopes": sorted(required_scopes)}

    try:
        return _request(account, path, params)
    except PinterestReadError as error:
        return {"error": str(error)}


def _endpoint(resource, arguments, options):
    if not isinstance(resource, str) or resource not in _RESOURCES:
        return {"error": "Этот ресурс Pinterest не поддерживается."}
    allowed_options = _OPTION_KEYS.get(resource, set())
    unknown = set(options) - allowed_options
    if unknown:
        return {"error": f"Для ресурса {resource} не документированы параметры: {', '.join(sorted(unknown))}."}
    missing = _REQUIRED_OPTIONS.get(resource, set()) - set(options)
    if missing:
        return {"error": f"Для ресурса {resource} требуются параметры: {', '.join(sorted(missing))}."}
    params = dict(options)
    if resource in _PAGINATED:
        try:
            page_size = int(arguments.get("page_size", 25))
        except (TypeError, ValueError):
            return {"error": "page_size должен быть целым числом от 1 до 250."}
        if not 1 <= page_size <= 250:
            return {"error": "Размер страницы Pinterest API должен быть от 1 до 250."}
        params["page_size"] = page_size
    if resource in _PAGINATED or resource in {"search_pins", "partner_pins"}:
        bookmark = arguments.get("bookmark")
        if bookmark is not None:
            if not isinstance(bookmark, str):
                return {"error": "bookmark должен быть строкой из предыдущего ответа Pinterest."}
            params["bookmark"] = bookmark
    if resource in {"analytics", "top_pins", "top_video_pins", "pin_analytics", "pins_analytics"}:
        date_error = _validate_date_range(params)
        if date_error:
            return date_error
    if resource in {"pin", "pin_tags", "pin_analytics"}:
        pin_id = str(arguments.get("pin_id", ""))
        if not re.fullmatch(r"\d{1,30}", pin_id):
            return {"error": "Передай pin_id, возвращённый Pinterest."}
    if resource in {"board", "sections", "board_pins", "section_pins"}:
        board_id = str(arguments.get("board_id", ""))
        if not re.fullmatch(r"\d{1,30}", board_id):
            return {"error": "Передай board_id, возвращённый Pinterest."}
    else:
        board_id = ""
    if resource == "section_pins":
        section_id = str(arguments.get("section_id", ""))
        if not re.fullmatch(r"\d{1,30}", section_id):
            return {"error": "Передай section_id, возвращённый Pinterest."}
    else:
        section_id = ""
    if resource == "media_item":
        media_id = str(arguments.get("media_id", ""))
        if not media_id or len(media_id) > 200:
            return {"error": "Передай media_id, возвращённый Pinterest."}
    else:
        media_id = ""
    if resource == "followed_interests":
        username = str(arguments.get("username", ""))
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", username):
            return {"error": "Передай username аккаунта Pinterest."}
    else:
        username = ""
    if resource == "trend_keywords":
        region = str(arguments.get("region", ""))
        trend_type = str(arguments.get("trend_type", ""))
        if not re.fullmatch(r"[A-Za-z0-9_+-]{1,40}", region) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", trend_type):
            return {"error": "Для поиска трендов укажи region и trend_type из Pinterest API."}
    else:
        region = trend_type = ""
    if resource == "delivery_metrics" and params.get("report_type") not in {"SYNC", "ASYNC"}:
        return {"error": "Для delivery_metrics укажи report_type SYNC или ASYNC."}
    path, scopes = _RESOURCES[resource]
    if resource == "partner_pins":
        try:
            limit = int(options.get("limit", 10))
        except (TypeError, ValueError):
            return {"error": "Для поиска partner Pins укажи limit от 1 до 25."}
        if not 1 <= limit <= 25:
            return {"error": "Для поиска partner Pins укажи limit от 1 до 25."}
        params["limit"] = limit
    if resource == "trend_keywords" and "limit" in params:
        if not isinstance(params["limit"], int) or not 1 <= params["limit"] <= 25:
            return {"error": "Для трендов укажи limit от 1 до 25."}
    if resource == "suggested_terms":
        term = params.get("term")
        if not isinstance(term, str) or not 1 <= len(term.strip()) <= 100:
            return {"error": "Для подсказок укажи term длиной от 1 до 100 символов."}
        params["term"] = term.strip()
        if "limit" in params and (not isinstance(params["limit"], int) or not 1 <= params["limit"] <= 10):
            return {"error": "Для подсказок укажи limit от 1 до 10."}
    if resource == "related_terms":
        terms = params.get("terms")
        if not isinstance(terms, list) or not 1 <= len(terms) <= 5 or any(
            not isinstance(term, str) or not 1 <= len(term.strip()) <= 100 for term in terms
        ):
            return {"error": "Для связанных запросов укажи список terms из 1–5 непустых фраз."}
        params["terms"] = [term.strip() for term in terms]
    path = path.format(
        board_id=board_id,
        section_id=section_id,
        pin_id=str(arguments.get("pin_id", "")),
        media_id=quote(media_id, safe=""),
        username=quote(username, safe=""),
        region=quote(region, safe=""),
        trend_type=quote(trend_type, safe=""),
    )
    if resource == "pins" and options.get("include_protected_pins"):
        scopes = scopes | {"pins:read_secret"}
    if resource in {"secret_boards", "search_pins"}:
        if resource == "search_pins":
            scopes = scopes | {"pins:read_secret"}
    return path, params if resource == "related_terms" else _encode_arrays(params), scopes


def _validate_date_range(params):
    try:
        start_date = date.fromisoformat(str(params.get("start_date", "")))
        end_date = date.fromisoformat(str(params.get("end_date", "")))
    except ValueError:
        return {"error": "Укажи start_date и end_date в формате YYYY-MM-DD."}
    today = timezone.now().date()
    if (
        start_date > end_date
        or start_date < today - timedelta(days=90)
        or end_date > today
        or (end_date - start_date).days > 90
    ):
        return {"error": "Pinterest принимает даты в UTC: не старше 90 дней, не позже сегодняшней даты, диапазон не более 90 дней."}
    return None


def _encode_arrays(params):
    return {key: ",".join(map(str, value)) if isinstance(value, list) else value for key, value in params.items()}


def _request(account, path, params):
    now = timezone.now()
    refreshed = False
    if account.access_token_expires_at <= now + timedelta(seconds=60):
        if not refresh_account_token(account):
            account.refresh_from_db()
            if account.status == PinterestAccount.Status.REAUTH_REQUIRED:
                raise PinterestReadError("Доступ Pinterest истёк. Переподключи аккаунт в настройках бизнеса.")
            raise PinterestReadError("Не удалось обновить доступ Pinterest. Повтори попытку позже.")
        account.refresh_from_db()
        refreshed = True
    response = _get(path, params, decrypt_token(account.access_token_encrypted))
    if response.status_code == 401:
        if not refreshed:
            if not refresh_account_token(account):
                account.refresh_from_db()
                if account.status == PinterestAccount.Status.REAUTH_REQUIRED:
                    raise PinterestReadError("Pinterest отклонил доступ. Переподключи аккаунт в настройках бизнеса.")
                raise PinterestReadError("Не удалось обновить доступ Pinterest. Повтори попытку позже.")
            account.refresh_from_db()
            response = _get(path, params, decrypt_token(account.access_token_encrypted))
        if response.status_code == 401:
            if path != "/user_account":
                profile = _get("/user_account", {}, decrypt_token(account.access_token_encrypted))
                if profile.status_code == 200:
                    raise PinterestReadError("Pinterest отклонил чтение этого ресурса (HTTP 401). Доступ к профилю работает; проверь разрешения приложения.")
                if profile.status_code != 401:
                    raise PinterestReadError("Pinterest отклонил чтение этого ресурса (HTTP 401). Состояние доступа к профилю не подтверждено.")
            marked_for_reconnect = PinterestAccount.objects.filter(
                pk=account.pk,
                status=PinterestAccount.Status.CONNECTED,
                access_token_encrypted=account.access_token_encrypted,
            ).update(
                status=PinterestAccount.Status.REAUTH_REQUIRED,
                last_auth_error="api_http_401_after_refresh",
                updated_at=timezone.now(),
            )
            if not marked_for_reconnect:
                raise PinterestReadError("Доступ Pinterest изменился во время запроса. Повтори попытку.")
            raise PinterestReadError("Pinterest отклонил доступ к аккаунту (HTTP 401). Переподключи его в настройках бизнеса.")
    if response.status_code != 200:
        raise PinterestReadError(f"Pinterest API вернул HTTP {response.status_code} для чтения данных.")
    try:
        return response.json()
    except ValueError as error:
        raise PinterestReadError("Pinterest API вернул некорректный JSON.") from error


def _get(path, params, access_token):
    try:
        return requests.get(
            f"{API_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=20,
        )
    except requests.RequestException as error:
        raise PinterestReadError("Pinterest API сейчас недоступен.") from error
