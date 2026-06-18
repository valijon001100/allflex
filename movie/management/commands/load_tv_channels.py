from django.core.management.base import BaseCommand

from movie.iptv_channels import (
    PRIMARY_COUNTRY,
    sync_all_tv_channels,
    sync_tv_channels_from_m3u,
)


class Command(BaseCommand):
    help = "IPTV telekanallarini m3u playlistlardan yuklaydi (O'zbekiston birinchi)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            default='',
            help='Bitta M3U fayl yo\'li',
        )
        parser.add_argument(
            '--country',
            default='',
            help='Bitta mamlakat kodi (masalan: uz, ru)',
        )
        parser.add_argument(
            '--all-countries',
            action='store_true',
            help='Barcha mamlakat kanallarini yuklash',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Avvalgi kanallarni o\'chirib, qayta yuklash',
        )

    def handle(self, *args, **options):
        if options['all_countries']:
            result = sync_all_tv_channels(replace=options['replace'])
            self.stdout.write(self.style.SUCCESS(
                f'{result["countries"]} mamlakat, {result["total"]} kanal, '
                f'{result["created"]} yangi, {result["updated"]} yangilandi'
            ))
            if result['failed']:
                self.stderr.write(self.style.WARNING(
                    f'{len(result["failed"])} mamlakat yuklanmadi'
                ))
            if result.get('skipped'):
                self.stdout.write('Barcha mamlakat kanallari allaqachon yuklangan.')
            return

        country = (options['country'] or PRIMARY_COUNTRY).lower()
        path = options['path'] or None

        if options['replace'] and not path:
            from movie.models import TvChannel
            TvChannel.objects.filter(country_code=country).delete()

        result = sync_tv_channels_from_m3u(path=path, country_code=country)
        self.stdout.write(self.style.SUCCESS(
            f'{result.get("country_code", country)}: {result["total"]} ta kanal, '
            f'{result["created"]} yangi, {result["updated"]} yangilandi'
        ))
