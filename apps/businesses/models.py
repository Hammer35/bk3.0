from django.db import models

from apps.core.models import BaseModel
from apps.workspaces.models import Workspace


class Business(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="businesses",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    website = models.URLField(blank=True)
    niche = models.CharField(max_length=200, blank=True)
    language = models.CharField(max_length=10, default="ru")
    market = models.CharField(max_length=80, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="unique_business_slug_per_workspace",
            ),
        ]

    def __str__(self):
        return self.name
