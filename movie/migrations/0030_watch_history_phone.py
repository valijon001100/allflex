from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('movie', '0029_alter_movie_uid_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Telefon'),
        ),
        migrations.CreateModel(
            name='WatchHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subscriber_code', models.CharField(blank=True, default='', max_length=10)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('watched_at', models.DateTimeField(auto_now_add=True)),
                ('movie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='watch_history', to='movie.movie')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='watch_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tomosha tarixi',
                'verbose_name_plural': 'Tomosha tarixi',
                'ordering': ['-watched_at'],
                'indexes': [models.Index(fields=['-watched_at'], name='movie_watch_watched_6f0a0d_idx'), models.Index(fields=['user', 'movie'], name='movie_watch_user_id_8c2f1a_idx')],
            },
        ),
    ]
