from django.core.management import call_command
from django.core.management.base import BaseCommand

from movie.models import Category, LiveStream, Movie


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
        if Category.objects.filter(parent__isnull=True).exists():
            self.stdout.write('Ma\'lumotlar allaqachon mavjud — o\'tkazib yuborildi.')
            self._ensure_movie_protection()
            return
        call_command('loaddata', 'initial_data', verbosity=2)
        self._ensure_movie_protection()
        self.stdout.write(self.style.SUCCESS(
            f'Yuklandi: {Movie.objects.count()} kino, '
            f'{Category.objects.count()} bo\'lim, '
            f'{LiveStream.objects.count()} jonli efir'
        ))
