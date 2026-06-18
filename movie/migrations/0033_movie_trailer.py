from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0032_rename_movie_watch_watched_6f0a0d_idx_movie_watch_watched_89231c_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='trailer_file',
            field=models.FileField(blank=True, null=True, upload_to='movies/trailers/%Y/%m/', verbose_name='Treler'),
        ),
        migrations.AddField(
            model_name='movie',
            name='trailer_telegram_file_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='movie',
            name='trailer_telegram_file_unique_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='movie',
            name='trailer_url',
            field=models.URLField(blank=True, default='', verbose_name='Treler URL'),
        ),
    ]
