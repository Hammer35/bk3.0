"""Validation and normalisation of a pin picture uploaded by a person.

The file is decoded with Pillow and re-encoded, so metadata (EXIF, GPS), embedded payloads and fake extensions
never reach the database or Pinterest. Messages are fixed sentences marked for translation.
"""
import hashlib
import io

from django.utils.translation import gettext_noop
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000
MIN_SIDE = 200
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
GOOD_RATIO = (0.5, 0.8)  # width / height around Pinterest's recommended 2:3


class ImageError(Exception):
    """Safe-to-show reason a picture was refused."""


def process_upload(uploaded) -> dict:
    raw = uploaded.read(MAX_BYTES + 1)
    if not raw:
        raise ImageError(gettext_noop("Файл пустой."))
    if len(raw) > MAX_BYTES:
        raise ImageError(gettext_noop("Файл больше 10 МБ."))
    try:
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with Image.open(io.BytesIO(raw)) as probe:
            image_format = probe.format
            width, height = probe.size
            probe.verify()
        if image_format not in ALLOWED_FORMATS:
            raise ImageError(gettext_noop("Допустимы изображения JPEG, PNG и WebP."))
        if width * height > MAX_PIXELS:
            raise ImageError(gettext_noop("Изображение слишком большое по числу пикселей."))
        if min(width, height) < MIN_SIDE:
            raise ImageError(gettext_noop("Изображение слишком маленькое: меньшая сторона должна быть не меньше 200 пикселей."))
        with Image.open(io.BytesIO(raw)) as picture:
            picture = ImageOps.exif_transpose(picture)
            picture.load()
            has_alpha = picture.mode in ("RGBA", "LA") or (picture.mode == "P" and "transparency" in picture.info)
            out = io.BytesIO()
            if has_alpha:
                picture.convert("RGBA").save(out, format="PNG", optimize=True)
                content_type = "image/png"
            else:
                picture.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
                content_type = "image/jpeg"
            width, height = picture.size
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, SyntaxError):
        raise ImageError(gettext_noop("Не удалось прочитать изображение: файл повреждён или это не картинка."))
    data = out.getvalue()
    if len(data) > MAX_BYTES:
        raise ImageError(gettext_noop("После обработки файл больше 10 МБ. Уменьшите изображение."))
    return {"data": data, "content_type": content_type, "width": width, "height": height, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def ratio_note(width: int, height: int) -> str:
    """A hint, not an error: Pinterest favours vertical pictures close to 2:3."""
    ratio = width / height if height else 0
    return "" if GOOD_RATIO[0] <= ratio <= GOOD_RATIO[1] else gettext_noop(
        "Pinterest лучше показывает вертикальные изображения с соотношением сторон около 2:3.")
