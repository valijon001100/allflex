# Generated manually — Telegram bot wizard steps

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0039_telegram_bot_draft'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegrambotdraft',
            name='step',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='telegrambotdraft',
            name='video_file_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='telegrambotdraft',
            name='video_file_unique_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
