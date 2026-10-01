"""Optional image review for product cards; disabled until API spending is approved."""

import io
import json
import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache
from gigachat.models import Chat, Messages, MessagesRole
from PIL import Image

from .models import WBImageAnalysis
from .providers import GigaChatProvider
from .wb_products import HEADERS, MAX_IMAGE_BYTES

logger = logging.getLogger(__name__)


class VisionReadError(Exception):
    pass


def _jpeg_for_vision(url: str) -> bytes:
    # URLs passed here are generated from a verified WB article and CDN basket.
    response = requests.get(url, headers=HEADERS, timeout=10, stream=True)
    response.raise_for_status()
    try:
        data = bytearray()
        for chunk in response.iter_content(64 * 1024):
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError("Image too large")
        with Image.open(io.BytesIO(data)) as image:
            image.thumbnail((1200, 1200))
            output = io.BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=80)
            return output.getvalue()
    finally:
        response.close()


def describe_product_images(images: list[dict]) -> list[dict]:
    """Describe each surviving image with one billed GigaChat 2 Pro call per image."""
    if not getattr(settings, "STRATEGIST_PRODUCT_VISION_ENABLED", False):
        return images
    if len(images) > 15:
        raise VisionReadError("Для анализа более 15 фото требуется отдельное подтверждение расходов.")
    client_provider = GigaChatProvider()
    reviewed = []
    with client_provider._client() as client:
        for item in images:
            image_id = None
            result = dict(item)
            record = WBImageAnalysis.objects.filter(sha256=item["sha256"]).first()
            if record and record.description:
                reviewed.append({**result, "description": record.description,
                                 "person": record.person, "person_wears_product": record.person_wears_product,
                                 "clean": record.clean, "reviewed": record.reviewed})
                continue
            cache_key = f"strategist:wb-vision:{item['sha256']}"
            saved = cache.get(cache_key)
            if isinstance(saved, dict) and saved.get("description"):
                record, _ = WBImageAnalysis.objects.get_or_create(
                    sha256=item["sha256"],
                    defaults={"description": saved["description"],
                              "machine_description": saved["description"],
                              "person": saved.get("person", False),
                              "person_wears_product": saved.get("person_wears_product", False),
                              "clean": saved.get("clean", False)},
                )
                reviewed.append({**result, "description": record.description,
                                 "person": record.person, "person_wears_product": record.person_wears_product,
                                 "clean": record.clean, "reviewed": record.reviewed})
                continue
            try:
                jpeg = _jpeg_for_vision(item["url"])
                uploaded = client.upload_file((f"wb-{item['index']}.jpg", jpeg, "image/jpeg"), purpose="general")
                image_id = uploaded.id_
                completion = client.chat(Chat(
                    model="GigaChat-2-Pro",
                    temperature=0.1,
                    max_tokens=300,
                    messages=[Messages(
                        role=MessagesRole.USER,
                        content=(
                            "Опиши только видимые детали товара на фото, по-русски, одним коротким предложением. "
                            "Укажи, виден ли человек, надет ли товар на человека, чистое ли фото для пина. "
                            "Не угадывай состав, свойства или личность. Ответ строго JSON: "
                            '{"description":"...","person":false,"person_wears_product":false,"clean":false}'
                        ),
                        attachments=[image_id],
                    )],
                ))
                raw = completion.choices[0].message.content.strip()
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and isinstance(parsed.get("description"), str):
                    result["description"] = parsed["description"].strip()[:400]
                    result["person"] = parsed.get("person") is True
                    result["person_wears_product"] = parsed.get("person_wears_product") is True
                    result["clean"] = parsed.get("clean") is True
                    if result["description"]:
                        record, _ = WBImageAnalysis.objects.get_or_create(
                            sha256=item["sha256"],
                            defaults={"description": result["description"],
                                      "machine_description": result["description"],
                                      "person": result["person"],
                                      "person_wears_product": result["person_wears_product"],
                                      "clean": result["clean"]},
                        )
                        result.update({"description": record.description,
                                       "person": record.person,
                                       "person_wears_product": record.person_wears_product,
                                       "clean": record.clean, "reviewed": record.reviewed})
                        cache.set(cache_key, {
                            key: result[key] for key in ("description", "person", "person_wears_product", "clean")
                        }, 7 * 24 * 3600)
            except Exception as error:
                logger.warning("WB image %s vision failed: %s", item["index"], type(error).__name__)
                result["vision_error"] = True
            finally:
                if image_id:
                    try:
                        client.delete_file(image_id)
                    except Exception:
                        pass
            reviewed.append(result)
    if any(not item.get("description") for item in reviewed):
        raise VisionReadError("Не удалось описать каждое фото. Неполный визуальный анализ не сохранён.")
    return reviewed


def prefer_model_photos(images: list[dict], category: str) -> list[dict]:
    apparel = any(word in category.casefold() for word in (
        "одежд", "плать", "брюк", "юбк", "куртк", "обув", "серьг", "кольц", "браслет",
        "украшен", "бижутер", "бус", "цепочк", "ожерел", "кулон", "подвеск", "аксессуар", "сумк", "очк",
    ))
    if not apparel or not images or not all("description" in item for item in images):
        return images
    worn = [item for item in images if item.get("person_wears_product") and item.get("clean")]
    return worn if worn else images
