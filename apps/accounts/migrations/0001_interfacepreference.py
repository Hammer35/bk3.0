from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="InterfacePreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "font_scale_percent",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (100, "100%"),
                            (105, "105%"),
                            (110, "110%"),
                            (115, "115%"),
                            (120, "120%"),
                            (125, "125%"),
                            (130, "130%"),
                            (135, "135%"),
                            (140, "140%"),
                            (145, "145%"),
                            (150, "150%"),
                            (155, "155%"),
                            (160, "160%"),
                            (165, "165%"),
                            (170, "170%"),
                            (175, "175%"),
                            (180, "180%"),
                            (185, "185%"),
                            (190, "190%"),
                            (195, "195%"),
                            (200, "200%"),
                        ],
                        default=100,
                        verbose_name="размер текста",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="дата создания"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="дата изменения"),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interface_preference",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "настройка интерфейса",
                "verbose_name_plural": "настройки интерфейса",
            },
        ),
        migrations.AddConstraint(
            model_name="interfacepreference",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    font_scale_percent__in=(
                        100,
                        105,
                        110,
                        115,
                        120,
                        125,
                        130,
                        135,
                        140,
                        145,
                        150,
                        155,
                        160,
                        165,
                        170,
                        175,
                        180,
                        185,
                        190,
                        195,
                        200,
                    )
                ),
                name="valid_interface_font_scale_percent",
            ),
        ),
    ]
