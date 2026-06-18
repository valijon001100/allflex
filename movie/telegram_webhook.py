import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TelegramChannelVideo
from .telegram_storage import extract_channel_video

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
    if secret:
        header = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if header != secret:
            return HttpResponseForbidden()

    try:
        update = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse('bad request', status=400)

    video_data = extract_channel_video(update)
    if video_data and video_data.get('file_id'):
        TelegramChannelVideo.objects.update_or_create(
            file_unique_id=video_data['file_unique_id'],
            defaults={
                'channel_id': video_data['channel_id'],
                'message_id': video_data['message_id'],
                'file_id': video_data['file_id'],
                'file_name': video_data.get('file_name', ''),
                'file_size': video_data.get('file_size'),
                'duration': video_data.get('duration'),
                'caption': video_data.get('caption', ''),
            },
        )
        logger.info('Telegram kanal videosi saqlandi: %s', video_data['file_unique_id'])

    return HttpResponse('ok')
