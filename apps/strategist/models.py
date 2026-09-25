import uuid

from django.conf import settings
from django.db import models

from apps.businesses.models import Business
from apps.core.models import BaseModel


def default_conversation_slug():
    return f"session-{uuid.uuid4().hex}"


class AIConversation(BaseModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="ai_conversations")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, default=default_conversation_slug, editable=False, unique=True)
    is_active = models.BooleanField(default=True)


class AIMessage(BaseModel):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ASSISTANT = "ASSISTANT", "Assistant"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    provider = models.CharField(max_length=32, blank=True)
    model = models.CharField(max_length=80, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("created_at",)
