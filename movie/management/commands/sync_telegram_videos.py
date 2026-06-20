import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from movie.telegram_storage import _api_url, process_telegram_update


class Command(BaseCommand):
    help = 'Kutilgan Telegram update\'larni getUpdates orqali import qilish (webhook o\'chirilgan bo\'lishi kerak)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Bir martada olinadigan update\'lar soni (max 100)',
        )

    def handle(self, *args, **options):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            self.stderr.write(self.style.ERROR('TELEGRAM_BOT_TOKEN yo\'q'))
            return

        limit = min(max(1, options['limit']), 100)

        info_resp = requests.post(_api_url('getWebhookInfo'), timeout=30)
        info = info_resp.json().get('result', {})
        if info.get('url'):
            self.stderr.write(self.style.WARNING(
                'Webhook faol: %s\n'
                'getUpdates ishlamaydi. Avval webhook o\'chiring yoki bot orqali yangi video yuboring.'
                % info['url'],
            ))

        offset = 0
        saved = 0
        processed = 0

        while True:
            resp = requests.post(
                _api_url('getUpdates'),
                json={'offset': offset, 'limit': limit, 'timeout': 0},
                timeout=30,
            )
            data = resp.json()
            if not data.get('ok'):
                self.stderr.write(self.style.ERROR(data.get('description', 'Xato')))
                return

            updates = data.get('result', [])
            if not updates:
                break

            for update in updates:
                processed += 1
                offset = update['update_id'] + 1
                if process_telegram_update(update):
                    saved += 1

        self.stdout.write(self.style.SUCCESS(
            f'Tayyor: {processed} update ko\'rildi, {saved} ta video saqlandi.',
        ))
