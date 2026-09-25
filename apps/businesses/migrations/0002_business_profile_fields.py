from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("businesses", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="audience",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="business",
            name="goals",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="business",
            name="subniche",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
