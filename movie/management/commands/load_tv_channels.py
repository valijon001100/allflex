from django.core.management.base import BaseCommand

from movie.iptv_channels import default_uz_playlist_path, sync_tv_channels_from_m3u


class Command(BaseCommand):
    help = "O'zbekiston IPTV kanallarini uz.m3u dan yuklaydi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            default='',
            help='M3U fayl yo\'li (standart: iptv-master/streams/uz.m3u)',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Avvalgi kanallarni o\'chirib, qayta yuklash',
        )

    def handle(self, *args, **options):
        path = options['path'] or None
        if path is None and not default_uz_playlist_path().is_file():
            self.stderr.write(self.style.ERROR(
                f'Fayl topilmadi: {default_uz_playlist_path()}'
            ))
            return

        result = sync_tv_channels_from_m3u(path=path, replace=options['replace'])
        self.stdout.write(self.style.SUCCESS(
            f'{result["path"]}: {result["total"]} ta kanal, '
            f'{result["created"]} yangi, {result["updated"]} yangilandi'
        ))
