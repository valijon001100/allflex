# Generated manually for Telegram bot auto movie import

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0038_tvchannel_country_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramBotDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField(db_index=True)),
                ('admin_user_id', models.BigIntegerField(blank=True, null=True)),
                ('media_group_id', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('poster_file_id', models.CharField(blank=True, default='', max_length=255)),
                ('poster_file_unique_id', models.CharField(blank=True, default='', max_length=255)),
                ('caption', models.TextField(blank=True, default='')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('is_complete', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Telegram bot draft',
                'verbose_name_plural': 'Telegram bot draftlar',
                'ordering': ['-updated_at'],
            },
        ),
    ]
