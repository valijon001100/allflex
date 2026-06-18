from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand

from movie.iptv_countries import POPULAR_COUNTRY_CODES
from movie.models import TvChannel
from movie.stream_probe import probe_stream_url


class Command(BaseCommand):
    help = "Telekanal streamlarini tekshiradi va ishlamaydiganlarini yashiradi"

    def add_arguments(self, parser):
        parser.add_argument('--country', default='', help='Bitta mamlakat (masalan: uz)')
        parser.add_argument(
            '--priority',
            action='store_true',
            help='Mashhur mamlakatlardagi kanallarni tekshirish',
        )
        parser.add_argument('--workers', type=int, default=8)
        parser.add_argument('--timeout', type=int, default=8)

    def handle(self, *args, **options):
        qs = TvChannel.objects.filter(is_active=True)
        country = (options['country'] or '').lower()
        if country:
            qs = qs.filter(country_code=country)
        elif options['priority']:
            qs = qs.filter(country_code__in=POPULAR_COUNTRY_CODES)

        channels = list(qs.only('id', 'name', 'stream_url', 'is_playable', 'country_code'))
        if not channels:
            self.stdout.write('Tekshiriladigan kanal yo\'q.')
            return

        timeout = options['timeout']
        workers = max(1, options['workers'])
        playable_ids = []
        broken_ids = []

        def check(channel):
            return channel.id, probe_stream_url(channel.stream_url, timeout=timeout)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(check, channel): channel for channel in channels}
            for future in as_completed(futures):
                channel_id, ok = future.result()
                if ok:
                    playable_ids.append(channel_id)
                else:
                    broken_ids.append(channel_id)

        if playable_ids:
            TvChannel.objects.filter(id__in=playable_ids).update(is_playable=True)
        if broken_ids:
            TvChannel.objects.filter(id__in=broken_ids).update(is_playable=False)

        scope = country or ('priority' if options['priority'] else 'barcha')
        self.stdout.write(self.style.SUCCESS(
            f'{scope}: {len(playable_ids)} ishlaydi, {len(broken_ids)} yashirildi'
        ))
