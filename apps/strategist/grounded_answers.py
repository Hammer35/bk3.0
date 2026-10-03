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
PIN_SPECS_URL = "https://help.pinterest.com/en/article/review-pin-specs"


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


def approved_pin_text_limits() -> dict[str, int]:
    source = _approved_source("pinterest-pin-text-specs.md")
    if not source or PIN_SPECS_URL not in source.source_links:
        return {}
    title = source.metadata.get("pin_title_max_characters")
    description = source.metadata.get("pin_description_max_characters")
    if type(title) is not int or type(description) is not int or title <= 0 or description <= 0:
        return {}
    return {r"заголов\w*|\btitle\b": title, r"описан\w*|\bdescription\b": description}


def grounded_pinterest_answer(question: str, *, previous_user_message: str = "", previous_assistant_message: str = "") -> str | None:
    text = question.casefold().strip()
    previous_text = previous_user_message.casefold().strip()
    if (re.search(r"\bcta\b|призыв", text) and re.search(r"гарант|100\s*%", text)
            and re.search(r"продаж|доход|рост|результат", text)
            and re.search(r"напиши|придумай|сделай|предложи", text)):
        source = _approved_source("pinterest-spam-prevention.md")
        if source and POLICY_URL in source.source_links:
            return (
                "Гарантия результата здесь не подтверждена, поэтому включать её в CTA не стоит. "
                "Нейтральный вариант: «Узнайте подробности →». "
                "Это не заявление о запрете отдельного слова, а проверка правдивости обещания.\n\n"
                f"{POLICY_SOURCE}"
            )
    length_intent = bool(re.search(
        r"длин\w*|лимит\w*|максим\w*|сколько\s+(?:символ\w*|слов\w*|знак\w*)|"
        r"\bдо\s+\d+\s*символ\w*|"
        r"(?:оптимальн\w*|рекоменду\w*)[^.!?]*(?:символ\w*|слов\w*|знак\w*)",
        text,
    ))
    length_topic = bool(re.search(r"заголов\w*|описан\w*|\btitle\b|\bdescription\b", text))
    length_followup = (
        bool(re.search(r"заголов\w*|описан\w*", previous_text))
        and bool(re.search(r"длин\w*|лимит\w*|символ\w*|слов\w*", previous_text))
        and bool(re.search(r"это\s+правил\w*|официальн\w*|откуда|источник", text))
    )
    if (length_intent and length_topic) or length_followup:
        scope_text = f"{previous_text} {text}" if length_followup else text
        if not re.search(r"напиши|придумай|составь|сгенерируй", text):
            source = _approved_source("pinterest-pin-text-specs.md")
            if source and PIN_SPECS_URL in source.source_links:
                if re.search(r"\bapi\b|\bапи\b|реклам\w*", scope_text):
                    return (
                        "Лимиты из Review Pin specs относятся к перечисленным там форматам пинов. "
                        "Этот источник не подтверждает контракт Pinterest API или лимиты всех рекламных форматов; "
                        "автоматически переносить туда число 800 нельзя. Нужна спецификация конкретного метода или формата.\n\n"
                        f"Источник: [Review Pin specs]({PIN_SPECS_URL})"
                    )
                title_max = source.metadata.get("pin_title_max_characters")
                description_max = source.metadata.get("pin_description_max_characters")
                if type(title_max) is int and type(description_max) is int and title_max > 0 and description_max > 0:
                    fields = []
                    field_text = f"{previous_text} {text}" if length_followup else text
                    if re.search(r"заголов\w*|\btitle\b", field_text):
                        fields.append(f"заголовок — до {title_max} символов")
                    if re.search(r"описан\w*|\bdescription\b", field_text):
                        fields.append(f"описание — до {description_max} символов")
                    return (
                        f"По справке Pinterest для пинов с изображением и видео: {'; '.join(fields)}. "
                        "Это максимум, а не обязательная или оптимальная длина. "
                        "Универсальную оптимальную длину эта справка не задаёт.\n\n"
                        f"Источник: [Review Pin specs]({PIN_SPECS_URL})"
                    )
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
    cta_reference = previous_text or previous_assistant_message.casefold()
    cta_policy_followup = (
        bool(re.search(r"\bcta\b|призыв", cta_reference))
        and bool(re.search(r"^а?\s*(?:это|такой|такая|такие)|^не\s+запрещ", text))
        and bool(re.search(r"запрещ|разреш|допуст|правил", text))
        and not re.search(r"реклам\w*", text)
    )
    if cta_policy_followup:
        source = _approved_source("pinterest-organic-cta-policy.md")
        if source and POLICY_URL in source.source_links and PIN_HELP_URL in source.source_links:
            return (
                "Общего запрета на обычный CTA нет. Призыв должен соответствовать товару "
                "и странице по ссылке, без обмана и неподтверждённых обещаний. "
                "Это вывод из опубликованных правил, а не одобрение конкретного пина модерацией.\n\n"
                f"Источники: [справка Pinterest]({PIN_HELP_URL}), "
                f"[Правила сообщества]({POLICY_URL})"
            )
    ordinary_cta_question = (
        bool(re.search(r"^можно\s+ли\s+написать", text))
        and bool(re.search(r"органическ\w*\s+pin|органическ\w*\s+пин", text))
        and bool(re.search(r"[«\"](?:посмотр\w*|узна\w*|откро\w*)\s+[^»\"\n]{1,50}[»\"]", text))
        and not re.search(r"гарант|скидк|процент|\d|леч|наркот|запрещ", text)
    )
    if ordinary_cta_question:
        source = _approved_source("pinterest-organic-cta-policy.md")
        if source and POLICY_URL in source.source_links:
            return (
                "Обычный призыв перейти к информации о товаре сам по себе не запрещён. "
                "Проверь, что фраза и ссылка соответствуют товару и не обещают неподтверждённого результата. "
                "Это вывод из опубликованных правил, а не одобрение конкретного пина модерацией.\n\n"
                f"{POLICY_SOURCE}"
            )
    if re.search(r"автокликер", text) and re.search(r"опубликуй|повторяй|блокир", text):
        source = _approved_source("pinterest-spam-prevention.md")
        if source and POLICY_URL in source.source_links:
            return (
                "Автокликер запускать и повторять действия в обход блокировки не буду. "
                "Для публикации нужен разрешённый Pinterest способ с его актуальными ограничениями; "
                "его доступность здесь не подтверждена. Это не запрет на все сторонние инструменты.\n\n"
                f"{POLICY_SOURCE}"
            )
    if re.search(r"спам", text) and re.search(r"уникал", text) and re.search(r"аккаунт", text):
        source = _approved_source("pinterest-spam-prevention.md")
        if source and POLICY_URL in source.source_links:
            draft = re.search(r'"text"\s*:\s*"([^"\n]+)"|«([^»\n]+)»', question)
            if not draft:
                return "Пришли сам текст пина. Уникальность относительно аккаунта без истории публикаций проверить нельзя."
            words = [word[:4] for word in re.findall(r"[а-яёa-z]{4,}", (draft[1] or draft[2]).casefold())]
            repeated = any(words.count(word) > 1 for word in set(words))
            lead = (
                "В тексте есть повторение близких ключевых слов — это признак возможной набивки. "
                if repeated else "По одному тексту окончательный вывод о спаме сделать нельзя. "
            )
            return (
                lead + "Уникальность для аккаунта без истории публикаций не проверена. "
                "Сделай описание естественным, используя только известные свойства товара; "
                "смешение языков само по себе не доказывает нарушение. Это оценка текста, а не одобрение модерацией.\n\n"
                f"{POLICY_SOURCE}"
            )
    if re.search(r"pinterest|пинтерест", text) and re.search(r"спам", text) and re.search(r"личн\w*\s+данн", text) and re.search(r"объясни|разбор|пишет", text):
        source = _approved_source("pinterest-community-guidelines.md")
        if source and POLICY_URL in source.source_links:
            return (
                "В правилах о спаме Pinterest ограничивает повторяющийся и вводящий в заблуждение контент, "
                "обманные ссылки и обход защитных мер. Само коммерческое назначение пина не означает спам. "
                "Правила о приватности ограничивают раскрытие личных данных других людей без согласия; "
                "нейтральный разбор этих правил допустим.\n\n"
                f"{POLICY_SOURCE}"
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
    daily_reference = previous_text or previous_assistant_message.casefold()
    daily_followup = bool(re.search(r"\b(?:пин\w*|pins?)\b", daily_reference)) and bool(
        re.search(r"ежедневн\w*|\bдень\b|сутки", daily_reference)
    ) and bool(re.search(r"ежедневн\w*|\bдень\b|сутки|откуда|источник", text)) and bool(
        re.search(r"лимит\w*|норм\w*|правил\w*|обязател\w*|источник", text)
    ) and not re.search(r"реклам\w*|api|техническ\w*", text)
    if daily_followup:
        text = f"{daily_reference} {text}"
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
                ("Ранее названное число не подтверждено как правило. " if daily_followup and not previous_text else "")
                + "В проверенной справке Pinterest нет обязательной нормы количества пинов в день. "
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
