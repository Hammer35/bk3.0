from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("strategist", "0004_alter_aiconversation_options_alter_aimessage_options_and_more")]

    operations = [
        migrations.AddField(
            model_name="aimessage",
            name="assets",
            field=models.JSONField(blank=True, default=dict, verbose_name="данные карточки в чате"),
        ),
    ]
