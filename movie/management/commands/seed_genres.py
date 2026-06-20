from django.core.management.base import BaseCommand

from movie.models import Genre

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


class Command(BaseCommand):
    help = 'Janrlar ro\'yxatini yaratadi yoki yangilaydi'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for slug, name, name_uz, name_en in GENRES:
            _, was_created = Genre.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'name_uz': name_uz,
                    'name_en': name_en,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Janrlar: {created} yangi, {updated} yangilandi'))
