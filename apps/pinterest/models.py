from django.conf import settings
from django.db import models

from apps.businesses.models import Business
from apps.core.models import BaseModel


class PinterestAccount(BaseModel):
    class Status(models.TextChoices):
        CONNECTED = "CONNECTED", "Подключён"
        REAUTH_REQUIRED = "REAUTH_REQUIRED", "Требуется переподключение"
        DISCONNECTED = "DISCONNECTED", "Отключён"

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="pinterest_accounts",
        verbose_name="бизнес",
    )
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="connected_pinterest_accounts",
        verbose_name="подключил",
    )
    pinterest_user_id = models.CharField(max_length=100, verbose_name="ID Pinterest")
    username = models.CharField(max_length=100, blank=True, verbose_name="имя пользователя Pinterest")
    access_token_encrypted = models.TextField(verbose_name="зашифрованный access token")
    refresh_token_encrypted = models.TextField(blank=True, verbose_name="зашифрованный refresh token")
    access_token_expires_at = models.DateTimeField(verbose_name="срок access token")
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="срок refresh token")
    granted_scopes = models.JSONField(default=list, verbose_name="выданные разрешения")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.CONNECTED, db_index=True)
    last_refresh_attempt_at = models.DateTimeField(null=True, blank=True)
    last_auth_error = models.CharField(max_length=200, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="дата отключения")

    class Meta:
        verbose_name = "аккаунт Pinterest"
        verbose_name_plural = "аккаунты Pinterest"
        constraints = [
            models.UniqueConstraint(
                fields=("pinterest_user_id",),
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_pinterest_user",
            ),
        ]

    def __str__(self):
        return f"@{self.username}" if self.username else self.pinterest_user_id

    @property
    def is_connected(self):
        return self.status == self.Status.CONNECTED
