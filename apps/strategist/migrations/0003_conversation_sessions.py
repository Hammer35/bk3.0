from django.db import migrations, models
from django.utils.text import slugify

import apps.strategist.models


def populate_conversation_slugs(apps, schema_editor):
    Conversation = apps.get_model("strategist", "AIConversation")
    Message = apps.get_model("strategist", "AIMessage")
    database = schema_editor.connection.alias

    for conversation in Conversation.objects.using(database).all().iterator():
        first_question = (
            Message.objects.using(database)
            .filter(conversation_id=conversation.pk, role="USER")
            .order_by("created_at", "pk")
            .values_list("content", flat=True)
            .first()
        )
        title = (first_question or "").strip()[:200]
        if not title and conversation.title != "Первичный диалог":
            title = conversation.title[:200]
        slug_base = slugify(title)[:180].rstrip("-") or "session"
        conversation.title = title
        conversation.slug = f"{slug_base}-{conversation.pk}"
        conversation.save(using=database, update_fields=["title", "slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("strategist", "0002_aimessage_usage_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiconversation",
            name="slug",
            field=models.CharField(blank=True, max_length=220, null=True),
        ),
        migrations.RunPython(populate_conversation_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="aiconversation",
            name="slug",
            field=models.SlugField(default=apps.strategist.models.default_conversation_slug, editable=False, max_length=220, unique=True),
        ),
        migrations.AlterField(
            model_name="aiconversation",
            name="title",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
