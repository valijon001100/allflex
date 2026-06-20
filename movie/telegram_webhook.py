import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .telegram_storage import process_telegram_update

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

    try:
        process_telegram_update(update)
    except Exception:
        logger.exception('Telegram update qayta ishlash xatosi')
        try:
            from .telegram_storage import send_bot_message, is_telegram_admin
            message = update.get('message') or update.get('callback_query', {}).get('message')
            user = (update.get('message') or {}).get('from') or update.get('callback_query', {}).get('from') or {}
            chat_id = (message or {}).get('chat', {}).get('id')
            if chat_id and is_telegram_admin(user.get('id')):
                send_bot_message(chat_id, '⚠️ Server xatosi. Deploy/migrate tekshiring.')
        except Exception:
            logger.exception('Telegram xato xabari yuborilmadi')

    return HttpResponse('ok')
