from django.db import migrations

GENRES = [
    ('komediya', 'Комедия', 'Komediya', 'Comedy'),
    ('drama', 'Драма', 'Drama', 'Drama'),
    ('tarixiy', 'Исторические', 'Tarixiy kinolar', 'Historical'),
    ('semejnyj', 'Семейный', 'Oilaviy kinolar', 'Family'),
    ('hujjatli', 'Документальные', 'Hujjatli filmlar', 'Documentary'),
    ('uzhasy', 'Ужасы', 'Ujasni kinolar', 'Horror'),
    ('musiqiy', 'Музыкальные', 'Musiqiy', 'Musical'),
    ('boevik', 'Боевик', 'Jangari kinolar', 'Action'),
    ('fantastika', 'Фантастика', 'Fantastika', 'Sci-Fi'),
    ('fentezi', 'Фэнтези', 'Fentezi', 'Fantasy'),
    ('triller', 'Триллер', 'Triller', 'Thriller'),
    ('priklyucheniya', 'Приключения', 'Sarguzasht', 'Adventure'),
    ('melodrama', 'Мелодрама', 'Melodrama', 'Romance'),
    ('kriminal', 'Криминал', 'Kriminal', 'Crime'),
    ('biografiya', 'Биография', 'Biografiya', 'Biography'),
    ('sport', 'Спорт', 'Sport', 'Sport'),
    ('voennyj', 'Военный', 'Harbiy', 'War'),
]


def seed_genres(apps, schema_editor):
    Genre = apps.get_model('movie', 'Genre')
    for slug, name, name_uz, name_en in GENRES:
        Genre.objects.update_or_create(
            slug=slug,
            defaults={'name': name, 'name_uz': name_uz, 'name_en': name_en},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0042_genre_translations'),
    ]

    operations = [
        migrations.RunPython(seed_genres, migrations.RunPython.noop),
    ]
