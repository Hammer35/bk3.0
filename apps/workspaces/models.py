from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Workspace(BaseModel):
    name = models.CharField(max_length=200, verbose_name="название рабочего пространства")
    slug = models.SlugField(max_length=220, unique=True, verbose_name="слаг")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_workspaces",
        verbose_name="создатель",
    )

    class Meta:
        verbose_name = "рабочее пространство"
        verbose_name_plural = "рабочие пространства"

    def __str__(self):
        return self.name


class Membership(BaseModel):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Владелец"
        ADMIN = "ADMIN", "Администратор"
        EDITOR = "EDITOR", "Редактор"
        VIEWER = "VIEWER", "Наблюдатель"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="рабочее пространство",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
        verbose_name="пользователь",
    )
    role = models.CharField(max_length=16, choices=Role.choices, verbose_name="роль")

    class Meta:
        verbose_name = "участник рабочего пространства"
        verbose_name_plural = "участники рабочих пространств"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                name="unique_workspace_membership",
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.workspace} ({self.role})"

    @property
    def can_manage_businesses(self):
        return self.role in BUSINESS_MANAGEMENT_ROLES


BUSINESS_MANAGEMENT_ROLES = (
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.EDITOR,
)
