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
