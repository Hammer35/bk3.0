import uuid

from django.db import models


class BaseModel(models.Model):
    """Common identity/timestamps for domain models."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name="публичный идентификатор")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="дата изменения")

    class Meta:
        abstract = True
