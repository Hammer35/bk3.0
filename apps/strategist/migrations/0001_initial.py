from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = [("businesses", "0002_business_profile_fields"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="AIConversation", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("title", models.CharField(default="Первичный диалог", max_length=200)), ("is_active", models.BooleanField(default=True)), ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_conversations", to="businesses.business")), ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name="AIMessage", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("role", models.CharField(choices=[("USER", "User"), ("ASSISTANT", "Assistant")], max_length=16)), ("content", models.TextField()), ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="strategist.aiconversation"))], options={"ordering": ("created_at",)}),
    ]
