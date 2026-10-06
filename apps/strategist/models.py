import uuid

from django.conf import settings
from django.db import models

from apps.businesses.models import Business
from apps.core.models import BaseModel


def default_conversation_slug():
    return f"session-{uuid.uuid4().hex}"


class AIConversation(BaseModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="ai_conversations", verbose_name="бизнес")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="создатель")
    title = models.CharField(max_length=200, blank=True, default="", verbose_name="название сессии")
    slug = models.SlugField(max_length=220, default=default_conversation_slug, editable=False, unique=True, verbose_name="слаг")
    is_active = models.BooleanField(default=True, verbose_name="активна")

    class Meta:
        verbose_name = "сессия ИИ-стратега"
        verbose_name_plural = "сессии ИИ-стратега"


class AIMessage(BaseModel):
    class Role(models.TextChoices):
        USER = "USER", "Пользователь"
        ASSISTANT = "ASSISTANT", "ИИ-стратег"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages", verbose_name="сессия")
    role = models.CharField(max_length=16, choices=Role.choices, verbose_name="отправитель")
    content = models.TextField(verbose_name="сообщение")
    assets = models.JSONField(default=dict, blank=True, verbose_name="данные карточки в чате")
    provider = models.CharField(max_length=32, blank=True, verbose_name="провайдер ИИ")
    model = models.CharField(max_length=80, blank=True, verbose_name="модель ИИ")
    prompt_tokens = models.PositiveIntegerField(default=0, verbose_name="токены запроса")
    completion_tokens = models.PositiveIntegerField(default=0, verbose_name="токены ответа")
    total_tokens = models.PositiveIntegerField(default=0, verbose_name="всего токенов")

    class Meta:
        ordering = ("created_at",)
        verbose_name = "сообщение ИИ-стратега"
        verbose_name_plural = "сообщения ИИ-стратега"


class WBImageAnalysis(BaseModel):
    sha256 = models.CharField(max_length=64, unique=True, verbose_name="хеш изображения")
    description = models.TextField(verbose_name="описание изображения")
    machine_description = models.TextField(blank=True, verbose_name="исходное описание модели")
    person = models.BooleanField(default=False, verbose_name="есть человек")
    person_wears_product = models.BooleanField(default=False, verbose_name="товар на человеке")
    clean = models.BooleanField(default=False, verbose_name="чистое фото")
    reviewed = models.BooleanField(default=False, verbose_name="описание проверено")
    model = models.CharField(max_length=80, default="GigaChat-2-Pro", verbose_name="модель анализа")

    class Meta:
        verbose_name = "анализ изображения WB"
        verbose_name_plural = "анализы изображений WB"


class Strategy(BaseModel):
    """Logical strategy object; content lives only in immutable StrategyVersion rows."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        ACTIVE = "ACTIVE", "Действует"
        ARCHIVED = "ARCHIVED", "В архиве"

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="strategies", verbose_name="бизнес")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, verbose_name="статус")
    active_version = models.ForeignKey(
        "StrategyVersion", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="действующая версия",
    )
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="дата архивации")

    class Meta:
        verbose_name = "стратегия"
        verbose_name_plural = "стратегии"


class StrategyVersion(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Черновик"
        CONFIRMED = "CONFIRMED", "Подтверждена"
        SUPERSEDED = "SUPERSEDED", "Заменена"
        REJECTED = "REJECTED", "Отклонена"

    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, related_name="versions", verbose_name="стратегия")
    number = models.PositiveIntegerField(verbose_name="номер версии")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, verbose_name="статус")
    goals = models.JSONField(default=list, blank=True, verbose_name="цели")
    priorities = models.JSONField(default=list, blank=True, verbose_name="приоритеты")
    keyword_clusters = models.JSONField(default=list, blank=True, verbose_name="группы ключевых слов")
    recommended_boards = models.JSONField(default=list, blank=True, verbose_name="рекомендуемые доски")
    content_directions = models.JSONField(default=list, blank=True, verbose_name="контентные направления")
    publishing_cadence = models.JSONField(default=dict, blank=True, verbose_name="частота публикаций")
    seasonal_plans = models.JSONField(default=list, blank=True, verbose_name="сезонные планы")
    exclusions = models.JSONField(default=list, blank=True, verbose_name="исключения пользователя")
    rationale = models.JSONField(default=list, blank=True, verbose_name="основания")
    hypotheses = models.JSONField(default=list, blank=True, verbose_name="гипотезы")
    missing_data = models.JSONField(default=list, blank=True, verbose_name="недостающие данные")
    sources = models.JSONField(default=list, blank=True, verbose_name="источники (manifest)")
    change_note = models.CharField(max_length=500, blank=True, verbose_name="что изменено")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="создатель",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="+", verbose_name="подтвердил",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="дата подтверждения")

    class Meta:
        ordering = ("strategy", "number")
        verbose_name = "версия стратегии"
        verbose_name_plural = "версии стратегии"
        constraints = [
            models.UniqueConstraint(fields=["strategy", "number"], name="unique_strategy_version_number"),
        ]
