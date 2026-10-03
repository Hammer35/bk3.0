"""Short source-backed answers for recurring factual Pinterest questions."""

import re

from django.conf import settings
from django.utils import timezone

from apps.knowledge.sources import load_source


POLICY_URL = "https://policy.pinterest.com/ru/community-guidelines"
POLICY_SOURCE = f"Источник: [Правила сообщества Pinterest]({POLICY_URL})"
PIN_HELP_URL = "https://help.pinterest.com/en/business/article/pin-performance-and-distribution"
ANALYTICS_URL = "https://help.pinterest.com/en/business/article/pinterest-analytics"
CONVERSIONS_URL = "https://help.pinterest.com/en/business/article/conversion-insights"
DEVELOPER_GUIDELINES_URL = "https://policy.pinterest.com/en/developer-guidelines"


def _approved_source(filename: str):
    try:
        source = load_source(
            settings.BASE_DIR / "docs/ai-knowledge/knowledge" / filename,
            project_root=settings.BASE_DIR,
        )
    except (OSError, ValueError):
        return None
    today = timezone.localdate()
    if (
        source.status != "approved" or source.scope != "global" or source.language != "ru"
        or not source.source_checked or source.source_checked > today
        or (source.effective_until and source.effective_until < today)
    ):
        return None
    return source


def grounded_pinterest_answer(question: str, *, previous_user_message: str = "") -> str | None:
    text = question.casefold().strip()
    previous_text = previous_user_message.casefold().strip()
    api_retention_question = bool(re.search(r"pinterest|пинтерест", text)) and bool(
        re.search(r"\bapi\b|\bапи\b", text)
    ) and bool(re.search(r"хран\w*|сохран\w*", text)) and bool(re.search(r"данн\w*|информац\w*", text))
    api_retention_followup = bool(re.search(r"pinterest|пинтерест", previous_text)) and bool(
        re.search(r"\bapi\b|\bапи\b", previous_text)
    ) and bool(re.search(r"хран\w*|сохран\w*", previous_text)) and bool(
        re.search(r"данн\w*|информац\w*", previous_text)
    ) and bool(re.search(r"90\s*(?:дн|дней)|все\s+(?:эти\s+)?данн\w*", text)) and bool(
        re.search(r"хран\w*|сохран\w*|разреш\w*", text)
    )
    if api_retention_question or api_retention_followup:
        source = _approved_source("pinterest-developer-data-use.md")
        if source and DEVELOPER_GUIDELINES_URL in source.source_links:
            citation = f"[Правила Pinterest для разработчиков]({DEVELOPER_GUIDELINES_URL})"
            if api_retention_followup:
                return (
                    "Нет. Общего разрешения хранить все данные Pinterest API 90 дней нет. "
                    "В разделе «The basics» хранение полученной через API информации запрещено, "
                    "кроме аналитики рекламных кампаний своего аккаунта или аккаунта с явно предоставленным доступом. "
                    f"Источник: {citation}"
                )
            return (
                "В проверенных правилах Pinterest для разработчиков нет общего срока хранения данных API «90 дней». "
                "Раздел «The basics» запрещает хранить полученную через API информацию, кроме аналитики "
                "рекламных кампаний своего аккаунта или аккаунта с явно предоставленным доступом; "
                "к остальным данным нужно обращаться через API заново. "
                f"Источник: {citation}"
            )
    catalog_followup = (
        bool(re.search(r"посмотр\w*\s+каталог", previous_text))
        and bool(re.search(r"\b(?:да|нет)\b|ответ\w*|основан\w*|пункт\w*|источник\w*", text))
        and not re.search(r"реклам\w*|друг\w*\s+фраз\w*", text)
    )
    if catalog_followup:
        text = f"{previous_text} {text}"
    catalog_cta = bool(re.search(r"посмотр\w*\s+каталог", text)) and bool(
        re.search(r"pinterest|пинтерест|\bпин\w*\b|\bpin\w*\b", text)
    ) and bool(re.search(r"призыв|\bcta\b|правил|запрещ|разреш|допуст", text))
    if catalog_cta:
        source = _approved_source("pinterest-organic-cta-policy.md")
        if source and POLICY_URL in source.source_links and PIN_HELP_URL in source.source_links:
            if catalog_followup:
                return (
                    "Нет. Отдельного запрета на фразу «Посмотрите каталог» в проверенных правилах "
                    "Pinterest нет. Основание: справка Pinterest рекомендует призывать сохранять "
                    "пины и подписываться, а раздел «Спам» Правил сообщества запрещает обманные ссылки.\n\n"
                    f"Источники: [справка Pinterest]({PIN_HELP_URL}), "
                    f"[Правила сообщества]({POLICY_URL})"
                )
            return (
                "Нет, сама фраза «Посмотрите каталог» не запрещена отдельным правилом Pinterest. "
                "В проверенных материалах нет пункта с этой фразой: справка Pinterest рекомендует "
                "призывать сохранять пины и подписываться, а раздел «Спам» Правил сообщества запрещает вводящие "
                "в заблуждение ссылки. Убедитесь, что ссылка действительно ведёт в обещанный каталог.\n\n"
                f"Источники: [справка Pinterest]({PIN_HELP_URL}), "
                f"[Правила сообщества]({POLICY_URL})"
            )
    clicks_and_orders = bool(re.search(r"исходящ\w*\s+клик\w*", text)) and bool(
        re.search(r"заказ\w*|продаж\w*", text)
    )
    sales_followup = bool(re.search(r"исходящ\w*\s+клик\w*", previous_text)) and bool(
        re.search(r"оцен\w*\s+продаж\w*|сколько\s+заказ\w*", text)
    ) and bool(re.search(r"без\s+данн\w*|только\s+по\s+клик\w*", text))
    if clicks_and_orders or sales_followup:
        source = _approved_source("pinterest-publishing-and-sales-faq.md")
        if source and ANALYTICS_URL in source.source_links and CONVERSIONS_URL in source.source_links:
            if sales_followup:
                return (
                    "Нет. Даже приблизительно посчитать продажи только по исходящим кликам "
                    "без данных о покупках или конверсиях нельзя: это будет догадка.\n\n"
                    f"Источники: [Pinterest Analytics]({ANALYTICS_URL}), "
                    f"[Conversion insights]({CONVERSIONS_URL})"
                )
            lead = "Нет, число" if re.search(r"можно\s+ли|можно\s+понять|получится\s+ли", text) else "Число"
            return (
                f"{lead} заказов по исходящим кликам неизвестно: клик показывает переход "
                "за пределы Pinterest, а не покупку. Нужны данные магазина или настроенные "
                "события покупки.\n\n"
                f"Источники: [Pinterest Analytics]({ANALYTICS_URL}), "
                f"[Conversion insights]({CONVERSIONS_URL})"
            )
    daily_followup = bool(re.search(r"\b(?:пин\w*|pins?)\b", previous_text)) and bool(
        re.search(r"ежедневн\w*|\bдень\b|сутки", previous_text)
    ) and bool(re.search(r"ежедневн\w*|\bдень\b|сутки", text)) and bool(
        re.search(r"лимит\w*|норм\w*|правил\w*|обязател\w*", text)
    ) and not re.search(r"реклам\w*|api|техническ\w*", text)
    if daily_followup:
        text = f"{previous_text} {text}"
    if (
        re.search(r"\b(?:пин\w*|pins?)\b", text)
        and re.search(r"\b(?:ежедневн\w*|день|сутки)\b", text)
        and re.search(r"\b(?:сколько|правил\w*|норм\w*|треб\w*|рекоменду\w*|лимит\w*|обязател\w*|устанавлива\w*)\b", text)
    ):
        source = _approved_source("pinterest-publishing-and-sales-faq.md")
        if source and PIN_HELP_URL in source.source_links:
            claimed_number = (
                "Число «10 ежедневно» тоже не могу подтвердить как требование. "
                if re.search(r"\b10\b", text) else ""
            )
            return (
                "В проверенной справке Pinterest нет обязательной нормы количества пинов в день. "
                f"{claimed_number}"
                "Pinterest советует регулярно создавать оригинальный контент, ориентируясь на неделю. "
                f"Источник: [справка Pinterest]({PIN_HELP_URL})"
            )

    policy_question = bool(re.search(r"правил\w*\s+сообществ\w*|community\s+guidelines", text))
    category_list = policy_question and bool(re.search(r"\b(?:какие|перечисли|назови)\b", text)) and bool(
        re.search(r"\b(?:темы|категории|материалы|контент)\b", text)
    )
    educational_explanation = bool(re.search(r"^(?:можно|допустимо|разрешено)\s+ли\b", text)) and bool(
        re.search(r"образовательн\w*|просветительн\w*", text)
    ) and bool(re.search(r"\b(?:пин\w*|pins?)\b", text)) and bool(
        re.search(r"объясн\w*|рассказ\w*", text)
    ) and bool(re.search(r"pinterest|пинтерест", text)) and bool(
        re.search(r"запрещ\w*|правил\w*", text)
    )
    if not category_list and not educational_explanation:
        return None

    source = _approved_source("pinterest-community-guidelines.md")
    if not source or POLICY_URL not in source.source_links:
        return None
    if category_list:
        return (
            "Правила Pinterest ограничивают продвижение опасных и регулируемых товаров, "
            "сексуальную эксплуатацию, насилие, травлю и ненависть, мошенничество, "
            "вредную дезинформацию, нарушение приватности и спам. Это не запрет на любое "
            "упоминание темы: в зависимости от содержания Pinterest может удалить материал "
            "или ограничить его распространение.\n\n"
            f"{POLICY_SOURCE}"
        )
    return (
        "Да, нейтрально объяснить правило в образовательном Pin можно; само упоминание темы "
        "не равно её продвижению. В таком Pin не должно быть инструкций или призывов к "
        "запрещённому действию. Pinterest оценивает конкретный материал по контексту, поэтому "
        "гарантировать его публикацию нельзя.\n\n"
        f"{POLICY_SOURCE}"
    )
