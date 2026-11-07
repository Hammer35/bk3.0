"""Explicit, temporary image review used to tune recommendation criteria."""

import base64
import csv
import io
import json
import logging
import re

from PIL import Image
from gigachat.models import Chat, Messages, MessagesRole

from . import pin_images
from .providers import GigaChatProvider
from .wb_review_seven import REVIEWS as ADDITIONAL_WB_REVIEWS

logger = logging.getLogger(__name__)

MAX_IMAGES = 15
MAX_TOTAL_BYTES = 30 * 1024 * 1024
SAVED_WB_CARD = "775851159"
SAVED_WB_REVIEW = {
    "01.webp": ("recommended", "Рекомендую", [
        "Показан полный комплект целиком: куртка и брюки хорошо различимы на спокойном фоне.",
        "Подходит как главный товарный кадр. На всех фото карточки формат 3:4; для Pinterest желательно проверить макет 2:3.",
    ]),
    "02.webp": ("recommended", "Рекомендую", [
        "Полный комплект надет на модель, силуэт и детали видны целиком.",
        "Хороший основной lifestyle-кадр; белая обувь и футболка дают контраст, но товар остаётся главным.",
    ]),
    "03.webp": ("not_recommended", "Не рекомендую", [
        "Инфографика, крупные надписи и несколько уменьшенных изображений перегружают кадр.",
        "Ранее Vision ошибочно отметил изображение как чистое: надписи видны на самом фото. Для Pinterest-контента лучше выбрать фото товара без такого текстового коллажа.",
    ]),
    "04.webp": ("acceptable", "Допустим", [
        "Куртка показана близко, хорошо видны молния, полосы и посадка.",
        "Брюки комплекта не показаны, поэтому это дополнительный кадр о верхе, а не главный пин полного костюма.",
    ]),
    "05.webp": ("acceptable", "Допустим", [
        "Чистое качественное фото; обе детали товара — куртка и брюки — видны в кадре.",
        "Куртка на плече, но комплект можно рассмотреть целиком; фото допустимо для пина.",
    ]),
    "06.webp": ("not_recommended", "Не рекомендую", [
        "Это размерная сетка с большим количеством текста и измерений.",
        "Не подходит как товарный пин для этой подборки.",
    ]),
    "07.webp": ("recommended", "Рекомендую", [
        "Комплект показан на модели в движении; одежда различима, кадр добавляет динамику к студийным позам.",
        "Подходит как lifestyle-пин. Перед публикацией проверьте, что обрезка ног и обуви сохраняет нужный вид товара.",
    ]),
    "08.webp": ("recommended", "Рекомендую", [
        "Полный комплект на модели, спокойный фон, одежда хорошо читается.",
        "Пригоден для пина; похож на другие ровные студийные кадры карточки, поэтому не стоит публиковать всю серию подряд.",
    ]),
    "09.webp": ("acceptable", "Допустим", [
        "Комплект виден целиком под другим углом.",
        "Кадр близок по фону и подаче к фото 02, 08 и 10. Оставьте его как вариант ракурса, если нужен выбор, но серия целиком будет однообразной.",
    ]),
    "10.webp": ("recommended", "Рекомендую", [
        "Понятный полный вид комплекта на модели, без текста и дополнительных вставок.",
        "Хороший каталожный пин; чередуйте его с более динамичными фото, чтобы публикации не повторялись визуально.",
    ]),
    "11.webp": ("not_recommended", "Не рекомендую", [
        "Крупный план показывает отдельный элемент товара — часть толстовки.",
        "По этому кадру нельзя оценить комплект целиком, поэтому для самостоятельного пина он не подходит.",
    ]),
    "12.webp": ("recommended", "Рекомендую", [
        "Динамичная поза, при этом куртка и брюки остаются различимы.",
        "Хорошо разнообразит ровные студийные кадры и подходит для lifestyle-пина.",
    ]),
    "13.webp": ("acceptable", "Допустим", [
        "Вид сзади показывает посадку и детали комплекта, которых нет на фронтальных фото.",
        "Используйте как дополнительный ракурс; сам по себе кадр менее информативен для первого знакомства с товаром.",
    ]),
    "14.webp": ("recommended", "Рекомендую", [
        "Куртка на модели показана близко и отчётливо, видны посадка и полосы.",
        "Подходит как дополнительный пин о верхней части комплекта; полный вид брюк здесь не главный.",
    ]),
    "15.webp": ("not_recommended", "Не рекомендую", [
        "То же: крупный план отдельного элемента товара, видны рука и часть кармана.",
        "Комплект целиком не показан, поэтому кадр не подходит для самостоятельного пина.",
    ]),
}
SAVED_WB_REVIEW_151286059 = {
    "01.webp": ("recommended", "Рекомендую", [
        "Джинсы целиком видны спереди: хорошо читаются высокая посадка, прямой силуэт и длина.",
        "Чистый кадр без текста и лишних предметов; подходит как основной пин товара.",
    ], "Модель в полный рост показывает чёрные джинсы спереди на светлом фоне."),
    "02.webp": ("acceptable", "Допустим", [
        "Джинсы показаны целиком и хорошо различимы.",
        "Поза и оформление почти повторяют фото 01; лучше выбрать один из этих двух кадров, чтобы подборка не выглядела однообразной.",
    ], "Похожий на фото 01 фронтальный кадр чёрных джинсов на модели."),
    "03.webp": ("recommended", "Рекомендую", [
        "Джинсы показаны целиком сзади, хорошо видны посадка и задние карманы.",
        "Дополняет фронтальные кадры полезным ракурсом; фон чистый, товар не обрезан.",
    ], "Вид чёрных джинсов сзади на модели в полный рост."),
    "04.webp": ("not_recommended", "Не рекомендую", [
        "Это крупный план пояса и кармана — целиком джинсы не видны.",
        "Как и в предыдущих примерах с отдельными деталями, кадр не объясняет внешний вид товара целиком; подпись на фото дополнительно отвлекает.",
    ], "Крупный план чёрных джинсов: пояс, карман и текстовая подпись."),
    "05.webp": ("recommended", "Рекомендую", [
        "Джинсы целиком видны спереди, силуэт и длина хорошо читаются.",
        "Кадр чистый и достаточно отличается от фото 01–02 позой и фоном.",
    ], "Фронтальный полный кадр чёрных джинсов на модели."),
    "06.webp": ("recommended", "Рекомендую", [
        "В кадре видны джинсы от пояса до низа; сам товар занимает основную часть изображения.",
        "Обрезанное лицо не мешает оценить эти джинсы, а ракурс показывает посадку и движение ткани.",
    ], "Чёрные джинсы на модели в движении, показаны от пояса до обуви."),
    "07.webp": ("recommended", "Рекомендую", [
        "Джинсы целиком различимы в непринуждённой lifestyle-позе.",
        "Кадр показывает посадку в движении и разнообразит студийные фронтальные ракурсы.",
    ], "Модель сидит на диване в чёрных джинсах; видны посадка и обе штанины."),
    "08.webp": ("not_recommended", "Не рекомендую", [
        "Это таблица размеров с плотным текстом и мелкими значениями, а не фото товара.",
        "По вашему правилу размерную сетку не рекомендуем как пин с товарным изображением.",
    ], "Инфографика с размерной таблицей для джинсов."),
}
SAVED_WB_REVIEW_1221114868 = {
    "01.webp": ("recommended", "Рекомендую", [
        "Крем и сыворотка показаны вместе, оба предмета крупные и хорошо различимы.",
        "Кадр чистый и качественный; текстовые подписи не перекрывают товар.",
    ], "Набор крема и сыворотки VOIS на контрастном фоне."),
    "02.webp": ("not_recommended", "Не рекомендую", [
        "В кадре подарочная коробка, но сами крем и сыворотка не показаны.",
        "По изображению нельзя рассмотреть товар из карточки.",
    ], "Синяя подарочная коробка с лентой в руках."),
    "03.webp": ("acceptable", "Допустим", [
        "Сравнение «до/после» наглядно показывает результат и может работать как дополнительный пин.",
        "Подписей немало, но сравнение остаётся понятным; важно не добавлять к кадру ещё текст.",
    ], "Коллаж с кожей лица до и после и рекламными подписями."),
    "04.webp": ("not_recommended", "Не рекомендую", [
        "Формат «до/после» допустим, но длинные списки текста занимают значительную часть кадра.",
        "Сравнение перегружено подписями; сократите текст, чтобы результат оставался главным.",
    ], "Сравнение кожи лица до и после с текстовыми тезисами."),
    "05.webp": ("not_recommended", "Не рекомендую", [
        "Формат «до/после» сам по себе подходит для пина о результате ухода.",
        "Но мелкие сравнительные вставки и многочисленные подписи перегружают изображение.",
    ], "Коллаж с фрагментами лица до и после."),
    "06.webp": ("acceptable", "Допустим", [
        "Оба предмета набора показаны достаточно крупно и различимы.",
        "Текстовых блоков много, поэтому это скорее дополнительный информационный пин, чем чистый главный кадр.",
    ], "Крем и сыворотка рядом с инфографикой об их назначении."),
    "07.webp": ("not_recommended", "Не рекомендую", [
        "Модель и текст о компонентах занимают больше внимания, чем товар.",
        "Показана сыворотка, но крем из набора не виден; полный комплект не представлен.",
    ], "Модель держит флакон сыворотки рядом с перечнем компонентов."),
    "08.webp": ("not_recommended", "Не рекомендую", [
        "Кадр перегружен мелкими текстовыми блоками и составом компонентов.",
        "Показан отдельный флакон сыворотки, а не оба предмета набора.",
    ], "Флакон сыворотки и модель на фоне инфографики о составе."),
    "09.webp": ("not_recommended", "Не рекомендую", [
        "Коллаж из лиц для разных типов кожи занимает весь кадр.",
        "Товар из карточки не показан.",
    ], "Инфографика с четырьмя типами кожи."),
    "10.webp": ("not_recommended", "Не рекомендую", [
        "Крупный план текстуры на руке, упаковки набора нет.",
        "Это деталь способа нанесения, а не изображение товара целиком.",
    ], "Текстура крема и сыворотки на руке с подписями."),
    "11.webp": ("not_recommended", "Не рекомендую", [
        "Показан процесс нанесения и лицо модели; упаковки обоих средств в кадре нет.",
        "Инструкция с несколькими текстовыми блоками не заменяет товарное фото.",
    ], "Инфографика с инструкцией утреннего и вечернего ухода."),
    "12.webp": ("not_recommended", "Не рекомендую", [
        "Основу изображения составляют сертификаты и текст о составе.",
        "Упаковки средств слишком малы и не являются главным объектом кадра.",
    ], "Сертификаты и описание состава рядом с маленькими изображениями упаковки."),
    "13.webp": ("not_recommended", "Не рекомендую", [
        "Показана коробка и проверка защитной пломбы, но не сами средства.",
        "Этот кадр не позволяет оценить крем и сыворотку из карточки.",
    ], "Синяя коробка набора с текстом о защитной пломбе."),
    "14.webp": ("not_recommended", "Не рекомендую", [
        "В кадре рекламируются наклейки и подарочные дополнения.",
        "Сами крем и сыворотка не показаны.",
    ], "Модель держит коробку с наклейками и текстом про бонус к заказу."),
    "15.webp": ("not_recommended", "Не рекомендую", [
        "Показаны размеры коробки, а не содержимое набора.",
        "Крем и сыворотка не видны, размерная разметка отвлекает от товара.",
    ], "Модель держит коробку с нанесёнными размерами."),
    "16.webp": ("not_recommended", "Не рекомендую", [
        "На карточке-сравнении изображены несколько других подарочных наборов.",
        "Нужный комплект крема и сыворотки среди множества мелких товаров не выделен.",
    ], "Инфографика с разными подарочными наборами косметики."),
    "17.webp": ("not_recommended", "Не рекомендую", [
        "Показаны разные подарочные наборы, а не комплект из исследуемой карточки.",
        "Изображение перегружено мелкими товарами и пояснениями.",
    ], "Сравнительная инфографика с несколькими наборами косметики."),
    "18.webp": ("not_recommended", "Не рекомендую", [
        "В кадре телефон с сайтом и кнопка с рекламным призывом.",
        "Крем и сыворотка не показаны как товарный комплект.",
    ], "Телефон с каталогом магазина на фоне ванной комнаты."),
}
SAVED_WB_CARDS = {
    "151286059": {
        "title": "Женские прямые джинсы с высокой посадкой",
        "summary": "8 изображений · чёрные джинсы",
        "url": "https://www.wildberries.ru/catalog/151286059/detail.aspx?targetUrl=MI",
        "owner_confirmed": True,
        "reviews": SAVED_WB_REVIEW_151286059,
    },
    "1221114868": {
        "title": "Антивозрастной набор крем и сыворотка для лица",
        "summary": "18 изображений · крем и сыворотка для лица",
        "url": "https://www.wildberries.ru/catalog/1221114868/detail.aspx",
        "reviews": SAVED_WB_REVIEW_1221114868,
    },
    SAVED_WB_CARD: {
        "title": "Спортивный костюм для мальчика",
        "summary": "15 изображений · спортивный костюм",
        "url": "https://www.wildberries.ru/catalog/775851159/detail.aspx?targetUrl=MI",
        "reviews": SAVED_WB_REVIEW,
    },
}
SAVED_WB_ACTIVE_CARDS = ("1221114868", "246438624", "280089359", "366505286", "366505285", "950377246", "950377247")
for article, title, summary in (
    ("246438624", "Набор шампунь и кондиционер", "27 изображений · уход за волосами"),
    ("280089359", "Набор средств для очищения кожи", "17 изображений · очищающие средства"),
    ("366505286", "Брюки парашюты", "11 изображений · серые"),
    ("366505285", "Брюки парашюты", "12 изображений · белые"),
    ("950377246", "Женские широкие брюки", "12 изображений · жёлтые"),
    ("950377247", "Женские широкие брюки", "12 изображений · розовые"),
):
    labels = {"recommended": "Рекомендую", "acceptable": "Допустим", "not_recommended": "Не рекомендую"}
    SAVED_WB_CARDS[article] = {
        "title": title,
        "summary": summary,
        "url": f"https://www.wildberries.ru/catalog/{article}/detail.aspx",
        "reviews": {
            f"{number:02d}.webp": (status, labels[status], [reason], "")
            for number, (status, reason) in enumerate(ADDITIONAL_WB_REVIEWS[article], 1)
        },
    }
ALLOWED_FLAGS = {"watermark", "collage", "text_heavy", "low_quality"}
SCORES = {
    "product_match": {"MATCH": 35, "UNCERTAIN": 15, "MISMATCH": 0},
    "visibility": {"MAIN": 25, "SECONDARY": 18, "PARTIAL": 8, "NONE": 0},
    "technical_quality": {"GOOD": 20, "ACCEPTABLE": 15, "POOR": 6, "UNUSABLE": 0},
    "composition": {"STRONG": 10, "ACCEPTABLE": 7, "WEAK": 3},
    "category_fit": {"STRONG": 10, "ACCEPTABLE": 7, "WEAK": 3},
}
BEFORE_AFTER_SCORES = {
    "product_match": {"MATCH": 20, "UNCERTAIN": 12, "MISMATCH": 0},
    "technical_quality": {"GOOD": 25, "ACCEPTABLE": 18, "POOR": 8, "UNUSABLE": 0},
    "composition": {"STRONG": 30, "ACCEPTABLE": 22, "WEAK": 8},
    "category_fit": {"STRONG": 25, "ACCEPTABLE": 18, "WEAK": 5},
}
LABELS = {
    "product_match": "Соответствие товару",
    "visibility": "Видимость товара",
    "technical_quality": "Техническое качество",
    "composition": "Композиция",
    "category_fit": "Соответствие категории",
}


class ImageReviewError(Exception):
    """Safe error to show on the review page."""


def _image_prompt(product_name, category):
    category_context = f" Категория товара: {category}." if category else ""
    return (
        f"Оцени изображение для Pinterest-пина о товаре «{product_name}».{category_context} "
        "Оцени только то, что реально видно на изображении. Верни только JSON: "
        '{"description":"коротко, что изображено","product_match":"MATCH|UNCERTAIN|MISMATCH",'
        '"content_type":"PRODUCT|BEFORE_AFTER|INFOGRAPHIC|DETAIL|OTHER",'
        '"visibility":"MAIN|SECONDARY|PARTIAL|NONE",'
        '"technical_quality":"GOOD|ACCEPTABLE|POOR|UNUSABLE",'
        '"composition":"STRONG|ACCEPTABLE|WEAK","category_fit":"STRONG|ACCEPTABLE|WEAK",'
        '"flags":[]} . '
        "MATCH — визуально тот же товар, UNCERTAIN — по фото нельзя уверенно решить, "
        "MISMATCH — явно другой товар. MAIN — товар главный и хорошо различим; SECONDARY — "
        "различим, но не главный; PARTIAL — закрыт или обрезан; NONE — неразличим. "
        "content_type — основной формат: PRODUCT, BEFORE_AFTER (сравнение результата до и после), "
        "INFOGRAPHIC, DETAIL или OTHER. Не отклоняй BEFORE_AFTER только потому, что упаковка товара "
        "не видна: такой кадр может быть дополнительным пином, если результат явно связан с товаром. "
        "Для BEFORE_AFTER оцени, понятно ли сравнение и не перегружено ли оно мелким или лишним текстом; "
        "простое сравнение до/после не считай collage. Ставь text_heavy только когда текст мешает восприятию. "
        "GOOD — чётко и хорошо освещено; ACCEPTABLE — небольшие недостатки; POOR — "
        "заметное размытие, шум или плохой свет; UNUSABLE — товар нельзя рассмотреть. "
        "Композиция и категория оцениваются по уместности изображения для Pinterest-пина этого товара. "
        "flags — только элементы из списка watermark, collage, text_heavy, low_quality; "
        "если их нет, верни пустой список. Не считай обычную небольшую надпись водяным знаком."
    )


def _parse_response(raw):
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise ImageReviewError("Модель вернула ответ, который нельзя разобрать. Попробуйте ещё раз.") from error
    enums = {
        "product_match": {"MATCH", "UNCERTAIN", "MISMATCH"},
        "content_type": {"PRODUCT", "BEFORE_AFTER", "INFOGRAPHIC", "DETAIL", "OTHER"},
        "visibility": {"MAIN", "SECONDARY", "PARTIAL", "NONE"},
        "technical_quality": {"GOOD", "ACCEPTABLE", "POOR", "UNUSABLE"},
        "composition": {"STRONG", "ACCEPTABLE", "WEAK"},
        "category_fit": {"STRONG", "ACCEPTABLE", "WEAK"},
    }
    if not isinstance(value, dict) or any(value.get(key) not in allowed for key, allowed in enums.items()):
        raise ImageReviewError("Модель вернула неполную оценку. Результат не засчитан.")
    description = value.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ImageReviewError("Модель не описала изображение. Результат не засчитан.")
    flags = value.get("flags", [])
    if not isinstance(flags, list):
        flags = []
    value["flags"] = sorted({flag for flag in flags if isinstance(flag, str) and flag in ALLOWED_FLAGS})
    value["description"] = description.strip()[:400]
    return value


def _recommendation(review):
    if review.get("content_type", "PRODUCT") == "BEFORE_AFTER":
        before_after_points = sum(
            BEFORE_AFTER_SCORES[key][review[key]]
            for key in BEFORE_AFTER_SCORES
        )
        if "text_heavy" in review["flags"]:
            before_after_points = max(0, before_after_points - 20)
        reasons = [
            "Формат «до/после» допустим как дополнительный пин, если сравнение связано с товаром и легко читается.",
            f"Техническое качество — {review['technical_quality']}; композиция — {review['composition']}; соответствие категории — {review['category_fit']}.",
        ]
        warnings = []
        if review["product_match"] == "UNCERTAIN":
            warnings.append("упаковка не видна, связь результата с товаром следует подтвердить по контексту карточки")
        if "text_heavy" in review["flags"]:
            warnings.append("текст перегружает сравнение")
        if review["product_match"] == "MISMATCH" or review["technical_quality"] == "UNUSABLE":
            reasons.insert(0, "Изображение не связано с товаром или качество не позволяет рассмотреть сравнение.")
            return before_after_points, "not_recommended", "Не рекомендую", reasons
        if before_after_points >= 80 and not warnings:
            return before_after_points, "recommended", "Рекомендую", reasons
        if before_after_points >= 60:
            return before_after_points, "acceptable", "Допустим", [*warnings, *reasons]
        return before_after_points, "not_recommended", "Не рекомендую", [*warnings, *reasons]

    points = sum(SCORES[key][review[key]] for key in SCORES)
    hard_reject = (
        review["product_match"] == "MISMATCH"
        or review["visibility"] == "NONE"
        or review["technical_quality"] == "UNUSABLE"
    )
    reasons = [
        f"{LABELS[key]} — {SCORES[key][review[key]]}/{max(SCORES[key].values())}"
        for key in SCORES
    ]
    if hard_reject:
        if review["product_match"] == "MISMATCH":
            reasons.insert(0, "На фото явно другой товар")
        elif review["visibility"] == "NONE":
            reasons.insert(0, "Товар неразличим")
        else:
            reasons.insert(0, "Качество не позволяет рассмотреть товар")
        return points, "not_recommended", "Не рекомендую", reasons
    warnings = []
    if review["product_match"] == "UNCERTAIN":
        warnings.append("совпадение товара не подтверждено уверенно")
    if review["flags"]:
        warnings.append("обнаружены признаки: " + ", ".join(review["flags"]))
    if points >= 80 and not warnings:
        return points, "recommended", "Рекомендую", reasons
    if points >= 60:
        why = "Можно оставить для ручной проверки: " + "; ".join(warnings) if warnings else "Фото пригодно, но не прошло порог автоматической рекомендации (80 баллов)."
        return points, "acceptable", "Допустим", [why, *reasons]
    return points, "not_recommended", "Не рекомендую", [f"Ниже порога ручного рассмотрения (60 баллов).", *reasons]


def _preview(data):
    with Image.open(io.BytesIO(data)) as image:
        image.thumbnail((520, 700))
        output = io.BytesIO()
        image.convert("RGB").save(output, "JPEG", quality=78, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def saved_wb_image_reviews():
    """Render saved WB samples with cached or manually reviewed descriptions."""
    from django.conf import settings

    from .models import WBImageAnalysis

    groups = []
    for article in SAVED_WB_ACTIVE_CARDS:
        card = SAVED_WB_CARDS[article]
        directory = settings.MEDIA_ROOT / "image-analysis-test" / article
        inventory_path = directory / "inventory.csv"
        if not inventory_path.is_file():
            continue
        with inventory_path.open(encoding="utf-8", newline="") as source:
            inventory = list(csv.DictReader(source))
        reviews = card["reviews"]
        hashes = [row["sha256"] for row in inventory if row.get("file") in reviews]
        cached = {record.sha256: record for record in WBImageAnalysis.objects.filter(sha256__in=hashes)}
        group = {
            "article": article,
            "title": card["title"],
            "summary": card["summary"],
            "url": card["url"],
            "items": [],
        }
        for row in inventory:
            filename = row.get("file", "")
            if filename not in reviews:
                continue
            path = directory / filename
            if not path.is_file():
                continue
            status, label, reasons, *description = reviews[filename]
            record = cached.get(row["sha256"])
            group["items"].append({
                "number": int(row["index"]),
                "name": filename,
                "preview": _preview(path.read_bytes()),
                "width": int(row["width"]),
                "height": int(row["height"]),
                "status": status,
                "label": label,
                "reasons": reasons,
                "description_label": "Сохранённое описание Vision" if record else "Описание кадра",
                "review": {"description": record.description if record else (description[0] if description else "Описание Vision не найдено в кэше.")},
                "cached_flags": ([
                    "человек: да" if record.person else "человек: нет",
                    "товар на человеке: да" if record.person_wears_product else "товар на человеке: нет",
                    "clean: true" if record.clean else "clean: false",
                ] if record else []),
            })
        if group["items"]:
            groups.append(group)
    return groups


def analyze_uploads(uploads, *, product_name, category="", business):
    if len(uploads) > MAX_IMAGES:
        raise ImageReviewError(f"За один запуск можно проверить не больше {MAX_IMAGES} изображений.")
    from .models import PinImage

    prepared, results = [], []
    seen_hashes = set()
    used_hashes = set(PinImage.objects.filter(
        pin_version__pin__business=business,
    ).values_list("sha256", flat=True))
    total_bytes = 0
    for number, upload in enumerate(uploads, start=1):
        try:
            image = pin_images.process_upload(upload)
        except pin_images.ImageError as error:
            raise ImageReviewError(f"Файл «{upload.name}»: {error}") from error
        total_bytes += image["size"]
        if total_bytes > MAX_TOTAL_BYTES:
            raise ImageReviewError("Общий размер обработанных изображений превышает 30 МБ.")
        item = {"number": number, "name": upload.name[:160], "image": image,
                "preview": _preview(image["data"])}
        row = {"number": number, "name": item["name"], "preview": item["preview"],
               "width": image["width"], "height": image["height"]}
        if image["sha256"] in seen_hashes:
            row.update({"status": "not_recommended", "label": "Не рекомендую",
                        "reasons": ["Точное повторение другого файла в этой загрузке."]})
            results.append(row)
        elif image["sha256"] in used_hashes:
            row.update({"status": "not_recommended", "label": "Не рекомендую",
                        "reasons": ["Это фото уже использовано в пине этого бизнеса."]})
            results.append(row)
        elif min(image["width"], image["height"]) < 600:
            row.update({"status": "not_recommended", "label": "Не рекомендую",
                        "reasons": ["Меньшая сторона меньше 600 пикселей."]})
            results.append(row)
        else:
            prepared.append(item)
        seen_hashes.add(image["sha256"])

    if not prepared:
        return sorted(results, key=lambda row: row["number"])

    try:
        with GigaChatProvider()._client() as client:
            for item in prepared:
                file_id = None
                row = {"number": item["number"], "name": item["name"], "preview": item["preview"],
                       "width": item["image"]["width"], "height": item["image"]["height"]}
                try:
                    with Image.open(io.BytesIO(item["image"]["data"])) as source:
                        jpeg = io.BytesIO()
                        source.convert("RGB").save(jpeg, "JPEG", quality=84, optimize=True)
                    uploaded = client.upload_file((f"test-{item['number']}.jpg", jpeg.getvalue(), "image/jpeg"),
                                                  purpose="general")
                    file_id = uploaded.id_
                    completion = client.chat(Chat(
                        model="GigaChat-2-Pro", temperature=0.1, max_tokens=450,
                        messages=[Messages(
                            role=MessagesRole.USER,
                            content=_image_prompt(product_name, category), attachments=[file_id])]))
                    review = _parse_response(completion.choices[0].message.content)
                    score, status, label, reasons = _recommendation(review)
                    row.update({"status": status, "label": label, "score": score, "reasons": reasons,
                                "review": review})
                except ImageReviewError as error:
                    row.update({"status": "error", "label": "Анализ не выполнен", "reasons": [str(error)]})
                except Exception as error:
                    logger.warning("Manual image review failed for image %s: %s", item["number"], type(error).__name__)
                    row.update({"status": "error", "label": "Анализ не выполнен",
                                "reasons": ["Не удалось получить оценку. Проверьте подключение и повторите запуск."]})
                finally:
                    if file_id:
                        try:
                            client.delete_file(file_id)
                        except Exception:
                            pass
                results.append(row)
    except ImageReviewError:
        raise
    except Exception as error:
        logger.warning("Image review provider is unavailable: %s", type(error).__name__)
        completed = {row["number"] for row in results}
        for item in prepared:
            if item["number"] not in completed:
                results.append({"number": item["number"], "name": item["name"], "preview": item["preview"],
                                "width": item["image"]["width"], "height": item["image"]["height"],
                                "status": "error", "label": "Анализ не выполнен",
                                "reasons": ["Не удалось подключиться к сервису анализа изображений."]})
    return sorted(results, key=lambda row: row["number"])
