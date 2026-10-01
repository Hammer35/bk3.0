"""Read a complete Wildberries brand or seller catalog for the strategist.

The brand page and the seller page are different catalogs. A brand may contain
products from many sellers, so callers must never treat the brand total as one
seller's assortment.
"""

import json
import logging
import re
import socket
import time
from collections import Counter
from datetime import datetime, timezone as dt_timezone
from urllib.parse import quote

import requests
from django.core.cache import cache
from gigachat.models import Function, FunctionParameters
from gigachat.models.function_parameters_property import FunctionParametersProperty


logger = logging.getLogger(__name__)
STORE_RE = re.compile(
    r"https?://(?:www\.)?wildberries\.ru/(?P<kind>brands|seller)/"
    r"(?P<slug>[A-Za-z0-9][A-Za-z0-9_-]*)(?:[/?#][^\s<>)\]]*)?",
    re.IGNORECASE,
)
SESSION_KEY = "strategist:wb-browser-session:v1"
HELPER_SOCKET = "/app/.wb_browser.sock"
MAX_PAGES = 100
PAGE_DELAY_SECONDS = 0.2
DEST = "-455222"


class WBStoreError(Exception):
    pass


def store_link(message: str) -> dict | None:
    match = STORE_RE.search(message)
    if not match:
        return None
    kind = "brand" if match.group("kind").lower() == "brands" else "seller"
    slug = match.group("slug")
    return {
        "kind": kind,
        "slug": slug,
        "url": f"https://www.wildberries.ru/{'brands' if kind == 'brand' else 'seller'}/{slug}",
    }


def _get(url: str, *, headers: dict | None = None, timeout: int = 20) -> requests.Response:
    # The donor uses a direct WB connection: proxy IPs often receive 403.
    with requests.Session() as session:
        session.trust_env = False
        return session.get(url, headers=headers, timeout=timeout)


def _static_json(url: str) -> dict:
    try:
        response = _get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=12)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WBStoreError("Не удалось прочитать сведения о магазине из WB.") from error
    if not isinstance(data, dict):
        raise WBStoreError("WB не вернул данные магазина в ожидаемом формате.")
    return data


def _resolve(link: dict) -> tuple[int, str]:
    slug = link["slug"]
    if link["kind"] == "brand":
        data = _static_json(
            "https://static-basket-01.wbbasket.ru/vol0/data/brands/"
            f"{quote(slug, safe='')}.json"
        )
        identifier = data.get("id")
        name = data.get("name")
    elif slug.isdigit():
        identifier, name = int(slug), f"Продавец {slug}"
    else:
        data = _static_json(
            "https://static-basket-01.wbbasket.ru/vol0/constructor-api/shops/v3/"
            f"{quote(slug, safe='')}.json"
        )
        identifier = data.get("supplierID")
        name = data.get("name") or f"Продавец {slug}"
    try:
        identifier = int(identifier)
    except (TypeError, ValueError) as error:
        raise WBStoreError("WB не подтвердил ID магазина по этой ссылке.") from error
    if identifier <= 0:
        raise WBStoreError("WB не подтвердил ID магазина по этой ссылке.")
    return identifier, str(name or slug).strip()


def _browser_session() -> dict:
    """Get a guest WB session from the local host browser process."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(100)
            connection.connect(HELPER_SOCKET)
            connection.sendall(b'{"action":"session"}\n')
            with connection.makefile("rb") as response:
                saved = json.loads(response.readline(32768))
        if isinstance(saved, dict) and all(
            saved.get(key) for key in ("token", "wbauid", "user_agent", "deviceid")
        ):
            return saved
        raise WBStoreError("Локальный браузер не получил сессию WB.")
    except (OSError, ValueError) as error:
        logger.warning("WB browser helper failed: %s", type(error).__name__)
        raise WBStoreError("Локальный браузер WB недоступен.") from error


def _session(*, force: bool = False) -> dict:
    if not force:
        saved = cache.get(SESSION_KEY)
        if isinstance(saved, dict) and saved.get("token") and saved.get("wbauid"):
            return saved
    saved = _browser_session()
    cache.set(SESSION_KEY, saved, 6 * 3600)
    return saved


def _catalog_url(kind: str, identifier: int, page: int) -> str:
    if kind == "brand":
        return (
            "https://www.wildberries.ru/__internal/u-catalog/brands/v4/catalog?"
            f"ab_testing=false&appType=1&brand={identifier}&curr=rub"
            f"&dest={DEST}&hide_dtype=15&hide_vflags=4294967296"
            f"&lang=ru&sort=popular&spp=30&page={page}"
        )
    return (
        "https://www.wildberries.ru/__internal/catalog/sellers/v4/catalog?"
        f"ab_testing=false&appType=1&curr=rub&dest={DEST}"
        "&hide_dtype=15&hide_vflags=4294967296&lang=ru"
        f"&page={page}&sort=popular&spp=30&supplier={identifier}&uclusters=0"
    )


def _catalog_page(kind: str, identifier: int, page: int, referer: str) -> dict:
    session = _session()
    for attempt in range(2):
        headers = {
            "User-Agent": session["user_agent"],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Referer": referer,
            "Origin": "https://www.wildberries.ru",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": (
                f"_wbauid={session['wbauid']}; "
                f"x_wbaas_token={session['token']}; _cp=1"
            ),
            "deviceid": session["deviceid"],
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        try:
            response = _get(_catalog_url(kind, identifier, page), headers=headers)
        except requests.RequestException as error:
            raise WBStoreError(f"WB недоступен на странице каталога {page}.") from error
        if response.status_code in (403, 498) and attempt == 0:
            session = _session(force=True)
            continue
        if response.status_code != 200:
            raise WBStoreError(f"WB отказал в чтении страницы каталога {page} (HTTP {response.status_code}).")
        try:
            data = response.json()
        except ValueError as error:
            raise WBStoreError(f"WB не вернул каталог в JSON на странице {page}.") from error
        if not isinstance(data, dict) or not isinstance(data.get("products"), list):
            raise WBStoreError(f"WB вернул некорректную страницу каталога {page}.")
        return data
    raise WBStoreError(f"Не удалось прочитать страницу каталога {page}.")


def _product(item: dict) -> dict | None:
    try:
        article = int(item.get("id"))
    except (TypeError, ValueError):
        return None
    if article <= 0:
        return None
    try:
        seller_id = int(item.get("supplierId") or 0)
    except (TypeError, ValueError):
        seller_id = 0
    prices = [
        size.get("price") or {} for size in (item.get("sizes") or [])
        if isinstance(size, dict)
    ]
    sale_kopecks = next(
        (price.get("product") for price in prices if price.get("product")), None
    )
    colors = [
        color.get("name") for color in (item.get("colors") or [])
        if isinstance(color, dict) and color.get("name")
    ]
    return {
        "article": article,
        "name": str(item.get("name") or "").strip(),
        "brand": str(item.get("brand") or "").strip(),
        "seller": str(item.get("supplier") or "").strip(),
        "seller_id": seller_id,
        "category": str(item.get("entity") or "").strip(),
        "subject_id": item.get("subjectId"),
        "price_rub": round(sale_kopecks / 100) if isinstance(sale_kopecks, (int, float)) else None,
        "rating": item.get("reviewRating"),
        "feedbacks": item.get("feedbacks"),
        "photo_count": item.get("pics"),
        "colors": colors,
        "url": f"https://www.wildberries.ru/catalog/{article}/detail.aspx",
    }


def read_store(link: dict) -> dict:
    """Return all available catalog pages and an explicit completeness flag."""
    identifier, name = _resolve(link)
    cache_key = f"strategist:wb-store:v1:{link['kind']}:{identifier}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    products = []
    seen = set()
    total = None
    pages = 0
    error = ""
    for page in range(1, MAX_PAGES + 1):
        try:
            data = _catalog_page(link["kind"], identifier, page, link["url"])
        except WBStoreError as failure:
            if not products:
                raise
            error = str(failure)
            break
        pages = page
        try:
            total = int(data.get("total"))
        except (TypeError, ValueError):
            error = "WB не сообщил общий размер каталога."
            break
        page_products = data["products"]
        for raw in page_products:
            if not isinstance(raw, dict):
                continue
            item = _product(raw)
            if item and item["article"] not in seen:
                seen.add(item["article"])
                products.append(item)
        if len(products) >= total:
            break
        if not page_products:
            error = "WB вернул пустую страницу до конца каталога."
            break
        if page == MAX_PAGES:
            error = f"Достигнут предел {MAX_PAGES} страниц каталога."
            break
        time.sleep(PAGE_DELAY_SECONDS)
    complete = total is not None and len(products) >= total and not error
    counts = Counter((item["seller_id"], item["seller"]) for item in products)
    result = {
        "kind": link["kind"], "id": identifier, "name": name, "url": link["url"],
        "reported_total": total, "loaded_total": len(products), "pages": pages,
        "complete": complete, "error": error,
        "sellers": [
            {"id": seller_id, "name": seller_name, "products_on_page": count}
            for (seller_id, seller_name), count in counts.most_common()
        ],
        "products": products,
        "retrieved_at": datetime.now(dt_timezone.utc).isoformat(),
    }
    cache.set(cache_key, result, 3600 if complete else 300)
    return result


def wb_store_function() -> Function:
    """Let the strategist inspect the saved complete catalog in small slices."""
    return Function(
        name="read_wb_store_data",
        description=(
            "Читает сохранённый в текущем чате каталог WB без нового обращения к WB. "
            "catalog=brand для всей страницы бренда или seller для магазина продавца. "
            "Поиск query по названию, бренду, артикулу; seller_id фильтрует продавца. "
            "Используй offset/limit для просмотра всех товаров по страницам. "
            "Не путай бренд и продавца и учитывай поле complete."
        ),
        parameters=FunctionParameters(
            type="object",
            properties={
                "catalog": FunctionParametersProperty(type="string", enum=["brand", "seller"]),
                "query": FunctionParametersProperty(type="string"),
                "seller_id": FunctionParametersProperty(type="integer"),
                "offset": FunctionParametersProperty(type="integer"),
                "limit": FunctionParametersProperty(type="integer"),
            },
            required=["catalog"],
        ),
    )


def read_wb_store_data(assets: dict, arguments: dict) -> dict:
    catalog = arguments.get("catalog")
    if catalog not in {"brand", "seller"}:
        return {"error": "Укажи catalog=brand или catalog=seller."}
    primary = assets.get("wb_store")
    if catalog == "brand":
        store = primary if isinstance(primary, dict) and primary.get("kind") == "brand" else None
    else:
        store = assets.get("wb_seller_store")
        if not store and isinstance(primary, dict) and primary.get("kind") == "seller":
            store = primary
    if not isinstance(store, dict):
        return {"error": "Этот каталог не загружен в текущем чате."}
    try:
        offset = int(arguments.get("offset", 0))
        limit = int(arguments.get("limit", 30))
        seller_id = int(arguments.get("seller_id", 0))
    except (TypeError, ValueError):
        return {"error": "offset, limit и seller_id должны быть целыми числами."}
    if offset < 0 or not 1 <= limit <= 50 or seller_id < 0:
        return {"error": "Укажи offset от 0, limit от 1 до 50 и неотрицательный seller_id."}
    query = str(arguments.get("query") or "").strip().casefold()
    products = [
        item for item in store.get("products", [])
        if isinstance(item, dict)
        and (not seller_id or item.get("seller_id") == seller_id)
        and (not query or query in " ".join(
            str(item.get(key) or "") for key in ("article", "name", "brand", "seller", "category")
        ).casefold())
    ]
    return {
        "catalog": catalog, "name": store["name"], "source_url": store["url"],
        "complete": store["complete"], "reported_total": store["reported_total"],
        "loaded_total": store["loaded_total"], "error": store.get("error", ""),
        "filtered_total": len(products),
        "offset": offset, "next_offset": offset + limit if offset + limit < len(products) else None,
        "products": products[offset:offset + limit],
    }
