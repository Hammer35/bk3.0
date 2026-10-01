import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("strategist", "0005_aimessage_assets")]

    operations = [
        migrations.CreateModel(
            name="WBImageAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="публичный идентификатор")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="дата изменения")),
                ("sha256", models.CharField(max_length=64, unique=True, verbose_name="хеш изображения")),
                ("description", models.TextField(verbose_name="описание изображения")),
                ("machine_description", models.TextField(blank=True, verbose_name="исходное описание модели")),
                ("person", models.BooleanField(default=False, verbose_name="есть человек")),
                ("person_wears_product", models.BooleanField(default=False, verbose_name="товар на человеке")),
                ("clean", models.BooleanField(default=False, verbose_name="чистое фото")),
                ("reviewed", models.BooleanField(default=False, verbose_name="описание проверено")),
                ("model", models.CharField(default="GigaChat-2-Pro", max_length=80, verbose_name="модель анализа")),
            ],
            options={"verbose_name": "анализ изображения WB", "verbose_name_plural": "анализы изображений WB"},
        ),
    ]
