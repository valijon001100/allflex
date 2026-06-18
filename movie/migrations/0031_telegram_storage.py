from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0030_watch_history_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='moviestream',
            name='telegram_file_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='moviestream',
            name='telegram_file_unique_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.CreateModel(
            name='TelegramChannelVideo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel_id', models.BigIntegerField()),
                ('message_id', models.BigIntegerField()),
                ('file_id', models.CharField(max_length=255)),
                ('file_unique_id', models.CharField(max_length=255, unique=True)),
                ('file_name', models.CharField(blank=True, default='', max_length=255)),
                ('file_size', models.BigIntegerField(blank=True, null=True)),
                ('duration', models.PositiveIntegerField(blank=True, null=True)),
                ('caption', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('linked_stream', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_source', to='movie.moviestream')),
            ],
            options={
                'verbose_name': 'Telegram video',
                'verbose_name_plural': 'Telegram videolar',
                'ordering': ['-created_at'],
            },
        ),
    ]
