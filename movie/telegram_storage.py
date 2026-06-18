import logging
import os
from typing import Iterator, Optional, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CLOUD_MAX_BYTES = 50 * 1024 * 1024
LOCAL_MAX_BYTES = 2 * 1024 * 1024 * 1024


class TelegramStorageError(Exception):
    pass


def telegram_configured() -> bool:
    return bool(
        getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        and getattr(settings, 'TELEGRAM_CHANNEL_ID', '')
    )


def telegram_local_api_enabled() -> bool:
    base = getattr(settings, 'TELEGRAM_API_BASE', 'https://api.telegram.org')
    return 'api.telegram.org' not in base


def max_upload_bytes() -> int:
    if telegram_local_api_enabled():
        return int(getattr(settings, 'TELEGRAM_MAX_UPLOAD_BYTES', LOCAL_MAX_BYTES))
    return int(getattr(settings, 'TELEGRAM_CLOUD_MAX_BYTES', CLOUD_MAX_BYTES))


def _upload_timeout(file_size: int) -> int:
    configured = int(getattr(settings, 'TELEGRAM_UPLOAD_TIMEOUT', 0) or 0)
    if configured:
        return configured
    size_mb = max(1, file_size // (1024 * 1024))
    return min(7200, max(600, size_mb * 3))


def _api_url(method: str) -> str:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise TelegramStorageError('TELEGRAM_BOT_TOKEN sozlanmagan.')
    base = getattr(settings, 'TELEGRAM_API_BASE', 'https://api.telegram.org').rstrip('/')
    return f'{base}/bot{token}/{method}'


def _file_url(file_path: str) -> str:
    token = settings.TELEGRAM_BOT_TOKEN
    base = getattr(settings, 'TELEGRAM_API_BASE', 'https://api.telegram.org').rstrip('/')
    return f'{base}/file/bot{token}/{file_path}'


def _request_api(method: str, timeout: int, **kwargs):
    try:
        response = requests.post(_api_url(method), timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise TelegramStorageError(f'Telegram API ulanish xatosi: {exc}') from exc
    data = response.json()
    if not data.get('ok'):
        description = data.get('description', 'Noma\'lum xato')
        raise TelegramStorageError(description)
    return data['result']


def _file_size(file_obj, file_path: str = '') -> int:
    if file_path and os.path.isfile(file_path):
        return os.path.getsize(file_path)
    size = getattr(file_obj, 'size', None)
    if size:
        return int(size)
    try:
        pos = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(pos)
        return int(size)
    except Exception:
        return 0


def _parse_upload_result(result: dict) -> Tuple[str, str]:
    media = result.get('video') or result.get('document')
    if not media:
        raise TelegramStorageError('Telegram javobida video topilmadi.')
    return media['file_id'], media.get('file_unique_id', '')


def format_file_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return '—'
    if size_bytes >= 1024 ** 3:
        return f'{size_bytes / (1024 ** 3):.2f} GB'
    if size_bytes >= 1024 ** 2:
        return f'{size_bytes / (1024 ** 2):.1f} MB'
    if size_bytes >= 1024:
        return f'{size_bytes / 1024:.0f} KB'
    return f'{size_bytes} B'


def build_movie_telegram_caption(
    movie,
    quality_label: str,
    file_size: int = 0,
    file_name: str = '',
) -> str:
    lines = [f'🎬 {movie.title}']

    if movie.title_uz and movie.title_uz.strip() != movie.title.strip():
        lines.append(f'🇺🇿 {movie.title_uz.strip()}')
    if movie.title_en and movie.title_en.strip() != movie.title.strip():
        lines.append(f'🇬🇧 {movie.title_en.strip()}')

    lines.append('')
    lines.append(f'📊 Sifat: {quality_label}')
    lines.append(f'📦 Hajm: {format_file_size(file_size)}')

    if file_name:
        lines.append(f'📁 Fayl: {os.path.basename(file_name)}')

    langs = []
    if movie.title:
        langs.append('RU')
    if movie.title_uz:
        langs.append('UZ')
    if movie.title_en:
        langs.append('EN')
    lines.append(f'🌐 Tillar: {", ".join(langs) or "RU"}')

    if movie.duration:
        lines.append(f'⏱ Davomiylik: {movie.duration}')
    if movie.year:
        lines.append(f'📅 Yil: {movie.year}')
    if movie.country:
        lines.append(f'🌍 Mamlakat: {movie.country}')

    category = getattr(movie, 'category', None)
    if category:
        cat_label = category.name
        if category.name_uz:
            cat_label = f'{category.name} / {category.name_uz}'
        lines.append(f'📂 Bo\'lim: {cat_label}')

    genre_names = []
    try:
        genre_names = list(movie.genres.values_list('name', flat=True)[:5])
    except Exception:
        pass
    if genre_names:
        lines.append(f'🎭 Janr: {", ".join(genre_names)}')

    if movie.rating:
        lines.append(f'⭐ Reyting: {movie.rating}')
    if movie.movie_uid:
        lines.append(f'🆔 ID: {movie.movie_uid}')
    if movie.is_premium:
        lines.append('💎 Premium')

    return '\n'.join(lines)[:1024]


def _local_api_path(abs_path: str) -> str:
    container_root = getattr(settings, 'TELEGRAM_LOCAL_MEDIA_ROOT', '').strip()
    if not container_root:
        return abs_path.replace('\\', '/')
    media_root = str(getattr(settings, 'MEDIA_ROOT', ''))
    if media_root and abs_path.startswith(media_root):
        rel = os.path.relpath(abs_path, media_root).replace('\\', '/')
        return f'{container_root.rstrip("/")}/{rel}'
    return abs_path.replace('\\', '/')


def _upload_by_local_path(abs_path: str, caption: str, file_size: int) -> Tuple[str, str]:
    channel_id = settings.TELEGRAM_CHANNEL_ID
    timeout = _upload_timeout(file_size)
    api_path = _local_api_path(abs_path)
    payload = {
        'chat_id': channel_id,
        'caption': (caption or '')[:1024],
        'document': api_path,
    }
    try:
        result = _request_api('sendDocument', timeout=timeout, json=payload)
    except TelegramStorageError:
        payload['video'] = abs_path
        del payload['document']
        result = _request_api('sendVideo', timeout=timeout, json=payload)
    return _parse_upload_result(result)


def _upload_streaming(
    file_obj,
    file_name: str,
    caption: str,
    file_size: int,
    force_document: bool = False,
) -> Tuple[str, str]:
    channel_id = settings.TELEGRAM_CHANNEL_ID
    timeout = _upload_timeout(file_size)
    file_obj.seek(0)
    caption = (caption or '')[:1024]

    if force_document or file_size > 45 * 1024 * 1024:
        files = {'document': (file_name, file_obj)}
        data = {'chat_id': channel_id, 'caption': caption}
        result = _request_api('sendDocument', timeout=timeout, data=data, files=files)
        return _parse_upload_result(result)

    files = {'video': (file_name, file_obj)}
    data = {'chat_id': channel_id, 'caption': caption, 'supports_streaming': True}
    try:
        result = _request_api('sendVideo', timeout=timeout, data=data, files=files)
    except TelegramStorageError:
        file_obj.seek(0)
        files = {'document': (file_name, file_obj)}
        result = _request_api(
            'sendDocument',
            timeout=timeout,
            data={'chat_id': channel_id, 'caption': caption},
            files=files,
        )
    return _parse_upload_result(result)


def upload_video_file(file_obj, caption: str = '', file_path: str = '') -> Tuple[str, str]:
    channel_id = settings.TELEGRAM_CHANNEL_ID
    if not channel_id:
        raise TelegramStorageError('TELEGRAM_CHANNEL_ID sozlanmagan.')

    abs_path = ''
    if file_path:
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            abs_path = ''

    file_size = _file_size(file_obj, abs_path)
    limit = max_upload_bytes()

    if file_size > limit:
        if telegram_local_api_enabled():
            raise TelegramStorageError(
                f'Fayl hajmi {file_size // (1024 ** 3)}GB — Telegram limiti '
                f'{limit // (1024 ** 3)}GB.',
            )
        raise TelegramStorageError(
            f'Fayl {file_size // (1024 ** 2)}MB. Cloud API limiti 50MB. '
            'GB videolar uchun TELEGRAM_API_BASE (Local Bot API) sozlang '
            'yoki videoni to\'g\'ridan-to\'g\'ri kanalga yuboring.',
        )

    if abs_path and telegram_local_api_enabled():
        logger.info('Telegram Local API orqali yuklanmoqda: %s (%s bytes)', abs_path, file_size)
        return _upload_by_local_path(abs_path, caption, file_size)

    if file_size > CLOUD_MAX_BYTES and not telegram_local_api_enabled():
        raise TelegramStorageError(
            f'Fayl {file_size // (1024 ** 2)}MB. Cloud API uchun maksimum 50MB. '
            'GB videolar uchun Local Bot API yoqing (TELEGRAM_API_BASE) '
            'yoki videoni Telegram ilovasi orqali kanalga yuboring.',
        )

    file_name = os.path.basename(abs_path) if abs_path else getattr(file_obj, 'name', 'video.mp4') or 'video.mp4'
    return _upload_streaming(file_obj, file_name, caption, file_size)


def get_download_url(file_id: str) -> str:
    result = _request_api('getFile', timeout=30, data={'file_id': file_id})
    remote_path = result.get('file_path')
    if not remote_path:
        raise TelegramStorageError('Telegram fayl yo\'li topilmadi.')
    return _file_url(remote_path)


def iter_telegram_stream(file_id: str, range_header: str = '') -> Tuple[Iterator[bytes], dict]:
    download_url = get_download_url(file_id)
    headers = {}
    if range_header:
        headers['Range'] = range_header
    try:
        upstream = requests.get(download_url, stream=True, headers=headers, timeout=120)
    except requests.RequestException as exc:
        raise TelegramStorageError(f'Video yuklab olish xatosi: {exc}') from exc
    if upstream.status_code not in (200, 206):
        raise TelegramStorageError(f'Telegram HTTP {upstream.status_code}')

    response_headers = {
        'Content-Type': upstream.headers.get('Content-Type', 'video/mp4'),
        'Accept-Ranges': 'bytes',
    }
    content_length = upstream.headers.get('Content-Length')
    content_range = upstream.headers.get('Content-Range')
    if content_length:
        response_headers['Content-Length'] = content_length
    if content_range:
        response_headers['Content-Range'] = content_range

    def generator():
        try:
            for chunk in upstream.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return generator(), response_headers


def extract_channel_video(update: dict) -> Optional[dict]:
    channel_id = str(getattr(settings, 'TELEGRAM_CHANNEL_ID', '') or '')
    if not channel_id:
        return None

    message = update.get('channel_post') or update.get('edited_channel_post')
    if not message:
        return None

    chat = message.get('chat') or {}
    if str(chat.get('id')) != channel_id:
        return None

    media = message.get('video') or message.get('document')
    if not media:
        return None

    mime = media.get('mime_type', '')
    if message.get('document') and mime and not mime.startswith('video/'):
        return None

    file_name = media.get('file_name', '')
    if message.get('document') and not mime.startswith('video/') and file_name:
        if not file_name.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.m4v', '.avi')):
            return None

    return {
        'channel_id': chat.get('id'),
        'message_id': message.get('message_id'),
        'file_id': media.get('file_id', ''),
        'file_unique_id': media.get('file_unique_id', ''),
        'file_name': file_name,
        'file_size': media.get('file_size'),
        'duration': media.get('duration'),
        'caption': (message.get('caption') or '')[:2000],
    }
