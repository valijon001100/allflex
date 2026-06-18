from django.core.management.base import BaseCommand

from movie.iptv_logos import download_logo_cache, refresh_channel_logos


class Command(BaseCommand):
    help = 'Telekanal logolarini iptv-org API dan yangilaydi'

    def add_arguments(self, parser):
        parser.add_argument(
            '--download-cache',
            action='store_true',
            help='API dan to\'liq logo cache faylini yuklab saqlash',
        )

    def handle(self, *args, **options):
        if options['download_cache']:
            total = download_logo_cache()
            self.stdout.write(self.style.SUCCESS(f'Cache saqlandi: {total} ta logo'))
        updated = refresh_channel_logos()
        self.stdout.write(self.style.SUCCESS(f'{updated} ta kanal logosi yangilandi'))
