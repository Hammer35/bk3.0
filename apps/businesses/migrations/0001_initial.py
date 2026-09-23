from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Business",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=220)),
                ("website", models.URLField(blank=True)),
                ("niche", models.CharField(blank=True, max_length=200)),
                ("language", models.CharField(default="ru", max_length=10)),
                ("market", models.CharField(blank=True, max_length=80)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")], default="ACTIVE", max_length=16)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="businesses", to="workspaces.workspace")),
            ],
        ),
        migrations.AddConstraint(
            model_name="business",
            constraint=models.UniqueConstraint(fields=("workspace", "slug"), name="unique_business_slug_per_workspace"),
        ),
    ]
