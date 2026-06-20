from django.core.management.base import BaseCommand
from django.conf import settings

import requests

from movie.telegram_storage import _api_url


class Command(BaseCommand):
    help = 'Telegram bot webhook URL ni sozlash'

    def handle(self, *args, **options):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        webhook_url = getattr(settings, 'TELEGRAM_WEBHOOK_URL', '')
        secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')

        if not token:
            self.stderr.write(self.style.ERROR('TELEGRAM_BOT_TOKEN yo\'q'))
            return
        if not webhook_url:
            self.stderr.write(self.style.ERROR('TELEGRAM_WEBHOOK_URL yo\'q (masalan: https://allflex.doccmed.uz/telegram/webhook/)'))
            return

        payload = {
            'url': webhook_url,
            'allowed_updates': [
                'callback_query',
                'channel_post',
                'edited_channel_post',
                'message',
                'edited_message',
            ],
        }
        if secret:
            payload['secret_token'] = secret

        response = requests.post(
            _api_url('setWebhook'),
            json=payload,
            timeout=30,
        )
        data = response.json()
        if data.get('ok'):
            self.stdout.write(self.style.SUCCESS(f'Webhook o\'rnatildi: {webhook_url}'))
        else:
            self.stderr.write(self.style.ERROR(data.get('description', 'Xato')))
