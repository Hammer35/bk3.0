from django.conf import settings
from django.db import models


FONT_SCALE_PERCENT_VALUES = tuple(range(100, 201, 5))
FONT_SCALE_PERCENT_CHOICES = tuple(
    (value, f"{value}%") for value in FONT_SCALE_PERCENT_VALUES
)


class InterfacePreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interface_preference",
        verbose_name="пользователь",
    )
    font_scale_percent = models.PositiveSmallIntegerField(
        choices=FONT_SCALE_PERCENT_CHOICES,
        default=100,
        verbose_name="размер текста",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="дата изменения")

    class Meta:
        verbose_name = "настройка интерфейса"
        verbose_name_plural = "настройки интерфейса"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(font_scale_percent__in=FONT_SCALE_PERCENT_VALUES),
                name="valid_interface_font_scale_percent",
            ),
        ]

    def __str__(self):
        return f"{self.user}: {self.font_scale_percent}%"
