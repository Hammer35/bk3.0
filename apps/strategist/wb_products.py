"""Read a Wildberries product linked in strategist chat.

WB's public basket CDN is not a stable API. Fail closed if a card or an image
cannot be verified; never turn missing product data into marketing claims.
"""

import hashlib
import io
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.core.cache import cache
from PIL import Image, UnidentifiedImageError


PRODUCT_URL_RE = re.compile(r"https?://(?:www\.)?wildberries\.ru/catalog/(\d+)/detail\.aspx(?:\?[^\s]*)?", re.I)
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,image/webp,*/*"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class ProductReadError(Exception):
    pass


def product_link(message: str) -> tuple[str, str] | None:
    match = PRODUCT_URL_RE.search(message)
    if not match:
        return None
    article = match.group(1)
    return article, f"https://www.wildberries.ru/catalog/{article}/detail.aspx"


def _card_path(article: str) -> str:
    number = int(article)
    return f"/vol{number // 100_000}/part{number // 1_000}/{article}/info/ru/card.json"


def _read_card(article: str) -> tuple[int, dict]:
    cached = cache.get(f"strategist:wb-card:{article}")
    if cached is not None:
        return cached
    estimate = max(1, math.ceil((int(article) // 100_000) / 258))
    first = [b for b in range(max(1, estimate - 5), min(60, estimate + 5) + 1)]
    remaining = [b for b in range(1, 61) if b not in first]

    def fetch(basket: int):
        url = f"https://basket-{basket:02d}.wbbasket.ru{_card_path(article)}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=6)
            if response.status_code == 200 and len(response.content) <= 2_000_000:
                data = response.json()
                if isinstance(data, dict) and str(data.get("nm_id")) == article:
                    return basket, data
        except (requests.RequestException, ValueError):
            pass
        return None

    for candidates in (first, remaining):
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = [pool.submit(fetch, basket) for basket in candidates]
            for future in as_completed(futures):
                found = future.result()
                if found:
                    cache.set(f"strategist:wb-card:{article}", found, 3600)
                    return found
    raise ProductReadError("Карточка WB недоступна или не найдена. Данные товара не подтверждены.")


def _fingerprint(content: bytes) -> tuple[str, int]:
    digest = hashlib.sha256(content).hexdigest()
    with Image.open(io.BytesIO(content)) as image:
        image = image.convert("L").resize((9, 8))
        pixels = list(image.getdata())
    difference = 0
    for row in range(8):
        for column in range(8):
            difference = (difference << 1) | (pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return digest, difference


def _image(article: str, basket: int, index: int):
    number = int(article)
    url = (
        f"https://basket-{basket:02d}.wbbasket.ru/vol{number // 100_000}"
        f"/part{number // 1_000}/{article}/images/big/{index}.webp"
    )
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, stream=True)
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_content(64 * 1024):
            content.extend(chunk)
            if len(content) > MAX_IMAGE_BYTES:
                raise ProductReadError("Фото товара превышает допустимый размер.")
        digest, visual_hash = _fingerprint(bytes(content))
        return {"url": url, "index": index, "sha256": digest, "dhash": visual_hash}
    except (requests.RequestException, UnidentifiedImageError, OSError, ValueError, ProductReadError):
        return None
    finally:
        if "response" in locals():
            response.close()


def read_product(article: str, url: str) -> dict:
    basket, card = _read_card(article)
    options = card.get("options") or []
    characteristics = [
        {"name": str(item["name"]).strip(), "value": str(item["value"]).strip()}
        for item in options
        if isinstance(item, dict) and item.get("name") and item.get("value")
    ]
    photo_count = (card.get("media") or {}).get("photo_count")
    if not isinstance(photo_count, int) or photo_count < 0 or photo_count > 100:
        raise ProductReadError("Количество фото в карточке WB не удалось проверить.")
    with ThreadPoolExecutor(max_workers=8) as pool:
        candidates = list(pool.map(lambda index: _image(article, basket, index), range(1, photo_count + 1)))
    for _ in range(2):
        missing = [index for index, candidate in enumerate(candidates, 1) if candidate is None]
        if not missing:
            break
        with ThreadPoolExecutor(max_workers=3) as pool:
            for index, candidate in zip(missing, pool.map(lambda i: _image(article, basket, i), missing)):
                candidates[index - 1] = candidate
    if any(candidate is None for candidate in candidates):
        raise ProductReadError("Не удалось получить все фото карточки WB. Повторите ссылку позже.")
    images = []
    duplicate_count = 0
    for candidate in candidates:
        if any(
            candidate["sha256"] == kept["sha256"]
            or (candidate["dhash"] ^ kept["dhash"]).bit_count() <= 4
            for kept in images
        ):
            duplicate_count += 1
            continue
        images.append(candidate)
    return {
        "article": article,
        "url": url,
        "title": str(card.get("imt_name") or "").strip(),
        "description": str(card.get("description") or "").strip(),
        "brand": str((card.get("selling") or {}).get("brand_name") or "").strip(),
        "category": str(card.get("subj_name") or "").strip(),
        "characteristics": characteristics,
        "photo_count": photo_count,
        "duplicate_count": duplicate_count,
        "images": images,
    }
