from django.core.management import call_command
from django.core.management.base import BaseCommand

from movie.models import Movie


class Command(BaseCommand):
    help = 'Boshlang\'ich kinolar va kategoriyalarni yuklaydi (faqat baza bo\'sh bo\'lsa)'

    def handle(self, *args, **options):
        if Movie.objects.exists():
            self.stdout.write('Ma\'lumotlar allaqachon mavjud — o\'tkazib yuborildi.')
            return
        call_command('loaddata', 'initial_data', verbosity=1)
        self.stdout.write(self.style.SUCCESS(
            f'Yuklandi: {Movie.objects.count()} ta kino'
        ))
