"""Server-side switches for Pinterest-related features that depend on Pinterest's approval."""
from django.conf import settings

COMPETITOR_RESEARCH_DISABLED_MESSAGE = (
    "Анализ конкурентов недоступен: функция требует письменного разрешения Pinterest."
)
AI_TRANSFER_DISABLED_MESSAGE = (
    "Передача данных Pinterest ИИ отключена настройкой: аналитика и тренды Pinterest "
    "в этом режиме не отправляются модели."
)


def competitor_research_enabled() -> bool:
    """Off unless explicitly enabled; no competitor feature exists in the code yet."""
    return bool(getattr(settings, "PINTEREST_COMPETITOR_RESEARCH_ENABLED", False))


def require_competitor_research_enabled() -> None:
    """Call first in any future competitor entry point, before Pinterest data is touched."""
    if not competitor_research_enabled():
        raise PermissionError(COMPETITOR_RESEARCH_DISABLED_MESSAGE)


def pinterest_ai_transfer_enabled() -> bool:
    """May Pinterest API data be sent to the LLM as transient inference context?"""
    return bool(getattr(settings, "PINTEREST_AI_DATA_TRANSFER_ENABLED", True))


def retention_days() -> int:
    return max(1, int(getattr(settings, "RESEARCH_SNAPSHOT_RETENTION_DAYS", 30)))


# Assistant messages whose text is made of Pinterest API data (direct answers, read errors) or of
# strategies/plans built from it. They are left out of the model's history while transfer is off.
PINTEREST_DERIVED_PROVIDERS = ("pinterest-api", "data-read", "strategy", "content-plan")


def require_pinterest_ai_transfer() -> None:
    """Defense in depth: stop any model call that would carry Pinterest data while transfer is off."""
    if not pinterest_ai_transfer_enabled():
        raise PermissionError(AI_TRANSFER_DISABLED_MESSAGE)
