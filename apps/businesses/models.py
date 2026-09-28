from django.db import models

from apps.core.models import BaseModel
from apps.workspaces.models import Workspace


class Business(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Активный"
        ARCHIVED = "ARCHIVED", "Архивный"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="businesses",
        verbose_name="рабочее пространство",
    )
    name = models.CharField(max_length=200, verbose_name="название бизнеса")
    slug = models.SlugField(max_length=220, verbose_name="слаг")
    website = models.URLField(blank=True, verbose_name="сайт")
    niche = models.CharField(max_length=200, blank=True, verbose_name="ниша")
    subniche = models.CharField(max_length=200, blank=True, verbose_name="подниша")
    language = models.CharField(max_length=10, default="ru", verbose_name="язык")
    market = models.CharField(max_length=80, blank=True, verbose_name="рынок")
    audience = models.TextField(blank=True, verbose_name="целевая аудитория")
    goals = models.TextField(blank=True, verbose_name="цели бизнеса")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="статус",
    )
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name="дата архивации")

    class Meta:
        verbose_name = "бизнес"
        verbose_name_plural = "бизнесы"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="unique_business_slug_per_workspace",
            ),
        ]

    def __str__(self):
        return self.name
