from django.db import migrations, models

MOVIE_TITLES_UZ = {
    1: 'Sonik 2 kinoda',
    2: 'Jasoratli talon-taroj: Tirilish uchun hamma narsa',
    3: 'Quyosh botishi',
    4: 'Egizak',
    5: 'Yirtib tashlash',
    6: 'Fleshbek',
    7: 'Sqrijet',
    8: 'Kung-fu',
    9: 'Absurd',
    10: 'Vokal-jinoiy ansambl',
    11: 'Nol bemor',
    12: 'Kumush bo\'ri',
    13: 'Ajoyib hikoya',
    14: 'Vendetta: Atlanta to\'dalari',
    15: 'Juft sayr',
    16: 'Doktor Kinzi',
    17: 'Xayr, janob Xoffman',
    18: 'Qattiq tarbiyali ota-onalar',
}


def populate_movie_titles(apps, schema_editor):
    Movie = apps.get_model('movie', 'Movie')
    Movie.objects.all().update(year='2026')
    for movie in Movie.objects.all():
        if movie.id in MOVIE_TITLES_UZ:
            movie.title_uz = MOVIE_TITLES_UZ[movie.id]
            movie.save(update_fields=['title_uz', 'year'])


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0017_category_name_en_category_name_uz_category_is_active_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='title_en',
            field=models.CharField(blank=True, default='', max_length=250, verbose_name='Title (EN)'),
        ),
        migrations.AddField(
            model_name='movie',
            name='title_uz',
            field=models.CharField(blank=True, default='', max_length=250, verbose_name='Nomi (UZ)'),
        ),
        migrations.AlterField(
            model_name='movie',
            name='title',
            field=models.CharField(max_length=250, verbose_name='Movie title (RU)'),
        ),
        migrations.RunPython(populate_movie_titles, migrations.RunPython.noop),
    ]
