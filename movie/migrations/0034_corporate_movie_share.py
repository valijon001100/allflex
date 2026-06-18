from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0033_movie_trailer'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorporateMovieShareLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, max_length=32, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('views_count', models.PositiveIntegerField(default=0)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movie_share_links', to='movie.corporatemember')),
                ('movie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='corporate_share_links', to='movie.movie')),
            ],
            options={
                'verbose_name': 'Korporativ kino havolasi',
                'verbose_name_plural': 'Korporativ kino havolalari',
                'unique_together': {('member', 'movie')},
            },
        ),
    ]
