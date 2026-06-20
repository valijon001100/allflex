from django.core.management.base import BaseCommand

from movie.models import Category, Movie


def fix_miscategorized_movies():
    moved = 0
    filmy = Category.objects.filter(slug='filmy').first()
    if not filmy:
        return moved

    tele = Category.objects.filter(slug='teleperedachi').first()
    if tele:
        moved += Movie.objects.filter(category=tele).update(category=filmy)

    return moved


class Command(BaseCommand):
    help = 'Noto\'g\'ri bo\'limga tushgan kinolarni tuzatadi (telekanallar -> filmlar)'

    def handle(self, *args, **options):
        moved = fix_miscategorized_movies()
        if moved:
            self.stdout.write(self.style.SUCCESS(
                f'{moved} ta kino Filmlar bo\'limiga ko\'chirildi.',
            ))
        else:
            self.stdout.write('Kino bo\'limlari tartibda.')
