from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0002_knowledgedocument_indexer_version")]

    operations = [
        migrations.AddField(
            model_name="knowledgechunk",
            name="fallback_embedding",
            field=models.JSONField(blank=True, default=list, verbose_name="резервное векторное представление"),
        ),
        migrations.AddField(
            model_name="knowledgechunk",
            name="fallback_embedding_model",
            field=models.CharField(blank=True, max_length=80, verbose_name="резервная модель эмбеддингов"),
        ),
    ]
