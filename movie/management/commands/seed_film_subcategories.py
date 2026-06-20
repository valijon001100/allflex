from django.core.management.base import BaseCommand

from movie.models import Category

FILM_SUBCATEGORIES = [
    ('serialy', 'Сериалы', 'Kino serial', 'TV Series', 1),
    ('ujalar', 'Ужасы', 'Ujalar', 'Horror', 2),
    ('anime', 'Аниме', 'Anime', 'Anime', 3),
    ('komediya', 'Комедии', 'Komediya', 'Comedy', 4),
    ('boevik', 'Боевики', 'Boevik', 'Action', 5),
    ('fantastika', 'Фантастика', 'Fantastika', 'Sci-Fi', 6),
    ('triller', 'Триллеры', 'Triller', 'Thriller', 7),
    ('skoro-na-sajte', 'Скоро на сайте', 'Tez kunda', 'Coming Soon', 99),
]


class Command(BaseCommand):
    help = 'Filmlar ichidagi yo\'nalishlar (ujalar, anime, serial...) bo\'limlarini yaratadi'

    def handle(self, *args, **options):
        filmy = Category.objects.filter(slug='filmy', parent__isnull=True).first()
        if not filmy:
            self.stderr.write(self.style.ERROR('filmy bo\'limi topilmadi'))
            return

        created = 0
        updated = 0
        for slug, name, name_uz, name_en, order in FILM_SUBCATEGORIES:
            obj, was_created = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    'parent': filmy,
                    'name': name,
                    'name_uz': name_uz,
                    'name_en': name_en,
                    'is_active': True,
                    'order': order,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Tayyor: {created} yangi, {updated} yangilangan ichki bo\'lim.',
        ))
