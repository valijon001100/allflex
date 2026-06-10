from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from movie.models import Movie, UserProfile


class Command(BaseCommand):
    help = 'Mavjud kinolar va foydalanuvchilarga himoya ID larini beradi'

    def handle(self, *args, **options):
        movies = 0
        for movie in Movie.objects.all():
            changed = movie.ensure_protection_ids()
            if changed:
                movie.save(update_fields=changed)
                movies += 1

        users = 0
        for user in User.objects.all():
            profile, created = UserProfile.objects.get_or_create(user=user)
            if profile.ensure_subscriber_code():
                profile.save(update_fields=['subscriber_code'])
                users += 1
            elif created:
                users += 1

        self.stdout.write(self.style.SUCCESS(
            f'Yangilandi: {movies} kino, {users} foydalanuvchi profili',
        ))
