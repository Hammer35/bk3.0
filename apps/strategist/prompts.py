from apps.businesses.models import Business


def build_strategist_system_prompt(business: Business) -> str:
    """Build the sole system instruction for a Business strategist conversation."""
    profile = {
        "Название": business.name,
        "Сайт": business.website or "не указан",
        "Ниша": business.niche or "не указана",
        "Подниша": business.subniche or "не указана",
        "Рынок": business.market or "не указан",
        "Аудитория": business.audience or "не указана",
        "Цели": business.goals or "не указаны",
    }
    business_context = "\n".join(f"{label}: {value}" for label, value in profile.items())
    return (
        "Ты ИИ-стратег BOOSTKLIENT. Помогаешь бизнесу планировать органический "
        "рост через Pinterest и превращать материалы карточек товаров в понятные "
        "контент-задачи. Отвечай по-русски, практично и структурированно. "
        "Не выдумывай факты о рынке, конкурентах или результатах. Если данных "
        "недостаточно, сначала задай короткий уточняющий вопрос.\n\n"
        "Профиль текущего бизнеса:\n"
        f"{business_context}"
    )
