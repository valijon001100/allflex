from django.core.management import call_command
from django.core.management.base import BaseCommand

from movie.models import Category, Genre, LiveStream, Movie


class Command(BaseCommand):
    help = 'Boshlang\'ich kinolar va kategoriyalarni yuklaydi (faqat baza bo\'sh bo\'lsa)'

    def _ensure_movie_protection(self):
        updated = 0
        for movie in Movie.objects.all():
            changed = movie.ensure_protection_ids()
            if changed:
                movie.save(update_fields=changed)
                updated += 1
        if updated:
            self.stdout.write(f'Himoya ID lari berildi: {updated} kino')

    def handle(self, *args, **options):
        if Category.objects.filter(parent__isnull=True).exists() or Movie.objects.exists():
            self.stdout.write('Ma\'lumotlar allaqachon mavjud — o\'tkazib yuborildi.')
            self._ensure_movie_protection()
            return

        # Migration/seed_genres janrlarni oldin yaratgan bo'lishi mumkin — fixture slug to'qnashuvini oldini olish.
        if Genre.objects.exists():
            self.stdout.write('Oldin yaratilgan janrlar tozalanmoqda (fixture yuklash uchun)...')
            Genre.objects.all().delete()

        call_command('loaddata', 'initial_data', verbosity=2)
        call_command('seed_genres')
        self._ensure_movie_protection()
        self.stdout.write(self.style.SUCCESS(
            f'Yuklandi: {Movie.objects.count()} kino, '
            f'{Category.objects.count()} bo\'lim, '
            f'{Genre.objects.count()} janr, '
            f'{LiveStream.objects.count()} jonli efir'
        ))
