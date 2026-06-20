"""
Telegram bot/kanal orqali film avtomatik yaratish.

Poster + video yuborish:
  1) Poster (rasm) + caption — nom, bo'lim, yil, tavsif
  2) Video — shu caption yoki poster xabariga reply

Yoki bitta video + caption (poster video thumbnail dan olinadi).

Caption namunasi:
  Inception
  Bo'lim: filmy
  Yil: 2010
  Tavsif: Ilmiy fantastika filmi
  Sifat: 720
"""
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify

from .telegram_storage import (
    TelegramStorageError,
    _file_url,
    _request_api,
    extract_bot_video,
    extract_channel_video,
    extract_video_from_message,
    is_telegram_admin,
    save_telegram_video,
    send_bot_message,
)

logger = logging.getLogger(__name__)

CAPTION_KEYS = {
    'title': ('nomi', 'nom', 'name', 'title', 'название', 'nazvanie', 'kino', 'film'),
    'title_uz': ('nomi uz', 'uz', 'o\'zbek', 'узбек'),
    'title_en': ('title en', 'en', 'english'),
    'category': ('bo\'lim', 'bolim', 'bo`lim', 'раздел', 'razdel', 'category', 'kategoriya', 'janr bo\'lim'),
    'year': ('yil', 'year', 'год', 'god'),
    'description': ('tavsif', 'description', 'описание', 'opisanie', 'about'),
    'quality': ('sifat', 'quality', 'качество', 'kachestvo'),
    'country': ('mamlakat', 'country', 'страна', 'strana'),
    'duration': ('davomiylik', 'duration', 'длительность', 'dlitelnost'),
    'type': ('tur', 'type', 'тип', 'tip'),
}


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace('`', "'").replace('’', "'")


def parse_movie_caption(caption: str) -> Dict[str, Any]:
    text = (caption or '').strip()
    meta: Dict[str, Any] = {}
    if not text:
        return meta

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    description_lines = []

    for line in lines:
        matched = False
        if ':' in line:
            key_part, value_part = line.split(':', 1)
            key_norm = _normalize_key(key_part)
            value = value_part.strip()
            if not value:
                continue
            for field, aliases in CAPTION_KEYS.items():
                if key_norm in aliases or any(key_norm == alias for alias in aliases):
                    meta[field] = value
                    matched = True
                    break
        if not matched and 'title' not in meta and not line.startswith('#'):
            meta['title'] = line
        elif not matched and not any(':' in ln and _normalize_key(ln.split(':', 1)[0]) in sum(CAPTION_KEYS.values(), ()) for ln in [line]):
            if ':' not in line:
                description_lines.append(line)

    if description_lines and 'description' not in meta:
        extra = '\n'.join(description_lines)
        if extra and extra != meta.get('title', ''):
            meta['description'] = extra

    if meta.get('quality'):
        q = re.sub(r'\D', '', str(meta['quality']))
        if q in ('480', '720', '1080', '2160'):
            meta['quality'] = '4k' if q == '2160' else q

    return meta


def _make_unique_slug(title: str) -> str:
    from .models import Movie

    try:
        from transliterate import translit
        base = slugify(translit(title, 'ru', reversed=True))
    except Exception:
        base = slugify(title)
    if not base:
        base = 'film'
    slug = base
    counter = 1
    while Movie.objects.filter(slug=slug).exists():
        counter += 1
        slug = f'{base}-{counter}'
    return slug


def fetch_telegram_file_content(file_id: str) -> Tuple[bytes, str]:
    result = _request_api('getFile', timeout=60, data={'file_id': file_id})
    remote_path = result.get('file_path', '')
    if not remote_path:
        raise TelegramStorageError('Telegram fayl yo\'li topilmadi.')
    url = _file_url(remote_path)
    try:
        response = requests.get(url, timeout=180)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TelegramStorageError(f'Fayl yuklab olinmadi: {exc}') from exc
    name = os.path.basename(remote_path.replace('\\', '/'))
    return response.content, name or 'file.bin'


def _resolve_category(raw: str):
    from django.db.models import Q
    from .models import Category

    value = (raw or '').strip()
    if not value:
        return Category.objects.filter(slug='filmy', is_active=True).first() or Category.objects.first()

    slug_candidate = slugify(value.replace('_', '-'))
    cat = Category.objects.filter(slug__iexact=slug_candidate).first()
    if cat:
        return cat

    cat = Category.objects.filter(
        Q(name__iexact=value) | Q(name_uz__iexact=value) | Q(name_en__iexact=value) | Q(slug__icontains=slug_candidate)
    ).first()
    if cat:
        return cat

    return Category.objects.filter(slug='filmy').first() or Category.objects.first()


def _get_or_create_draft(chat_id, media_group_id='', admin_user_id=None):
    from .models import TelegramBotDraft
    from django.utils import timezone
    from datetime import timedelta

    qs = TelegramBotDraft.objects.filter(chat_id=chat_id, is_complete=False)
    if media_group_id:
        draft = qs.filter(media_group_id=media_group_id).first()
        if draft:
            return draft
    draft = qs.filter(updated_at__gte=timezone.now() - timedelta(hours=2)).order_by('-updated_at').first()
    if draft and not media_group_id:
        return draft
    return TelegramBotDraft.objects.create(
        chat_id=chat_id,
        admin_user_id=admin_user_id,
        media_group_id=media_group_id or '',
    )


def _extract_photo_ids(message: dict) -> Tuple[str, str]:
    photos = message.get('photo') or []
    if not photos:
        return '', ''
    best = max(photos, key=lambda item: item.get('file_size', 0) or 0)
    return best.get('file_id', ''), best.get('file_unique_id', '')


def _video_thumb_file_id(message: dict) -> str:
    media = message.get('video') or message.get('document') or {}
    thumb = media.get('thumb') or media.get('thumbnail') or {}
    return thumb.get('file_id', '')


def _merge_metadata(draft_meta: dict, caption_meta: dict) -> dict:
    merged = dict(draft_meta or {})
    merged.update({k: v for k, v in (caption_meta or {}).items() if v})
    return merged


def _site_url(path: str) -> str:
    base = getattr(settings, 'SITE_BASE_URL', '') or ''
    if not base:
        origins = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])
        for origin in origins:
            if origin.startswith('https://') and 'onrender.com' not in origin:
                base = origin.rstrip('/')
                break
        if not base and origins:
            base = origins[0].rstrip('/')
    if not base:
        allowed = getattr(settings, 'ALLOWED_HOSTS', [])
        host = next((h for h in allowed if h and h not in ('*', 'localhost', '127.0.0.1')), '')
        if host:
            base = f'https://{host}'
    if not base:
        base = 'https://allflex.doccmed.uz'
    return f'{base.rstrip("/")}{path}'


def create_movie_from_telegram(
    *,
    video_data: dict,
    metadata: dict,
    poster_file_id: str,
    tg_video_record=None,
) -> Optional['Movie']:
    from .models import Movie, MovieStream

    title = (metadata.get('title') or '').strip()
    if not title:
        title = (video_data.get('file_name') or '').rsplit('.', 1)[0].strip()
    if not title:
        title = (video_data.get('caption') or '').splitlines()[0].strip() if video_data.get('caption') else ''
    if not title:
        return None

    if not poster_file_id:
        return None

    category = _resolve_category(metadata.get('category', ''))
    if not category:
        return None

    quality = metadata.get('quality') or '720'
    if quality not in ('480', '720', '1080', '4k'):
        quality = '720'

    media_type = _normalize_key(metadata.get('type', 'kino'))
    is_trailer = media_type in ('treler', 'trailer', 'трейлер', 'treyler')

    description = (metadata.get('description') or video_data.get('caption') or title).strip()
    year = str(metadata.get('year') or '2026')[:5]
    country = (metadata.get('country') or 'USA')[:50]
    duration = (metadata.get('duration') or '')[:50]

    try:
        poster_bytes, poster_name = fetch_telegram_file_content(poster_file_id)
    except TelegramStorageError as exc:
        logger.warning('Poster yuklanmadi: %s', exc)
        return None

    ext = os.path.splitext(poster_name)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
        poster_name = f'{slugify(title) or "poster"}.jpg'

    movie = Movie(
        title=title,
        title_uz=(metadata.get('title_uz') or '')[:250],
        title_en=(metadata.get('title_en') or '')[:250],
        slug=_make_unique_slug(title),
        category=category,
        description=description,
        short_description=description[:550],
        year=year,
        country=country,
        duration=duration,
        quality=quality if not is_trailer else 'Treler',
    )
    movie.poster.save(poster_name, ContentFile(poster_bytes), save=False)
    movie.save()

    if tg_video_record is None:
        tg_video_record, _ = save_telegram_video(video_data)

    if is_trailer:
        movie.trailer_telegram_file_id = video_data['file_id']
        movie.trailer_telegram_file_unique_id = video_data['file_unique_id']
        movie.save(update_fields=['trailer_telegram_file_id', 'trailer_telegram_file_unique_id'])
    else:
        stream, _ = MovieStream.objects.get_or_create(movie=movie, quality=quality)
        stream.telegram_file_id = video_data['file_id']
        stream.telegram_file_unique_id = video_data['file_unique_id']
        stream.url = ''
        stream.save()
        tg_video_record.linked_stream = stream
        tg_video_record.save(update_fields=['linked_stream'])

    logger.info('Telegram orqali film yaratildi: %s (pk=%s)', movie.title, movie.pk)
    return movie


def _handle_photo_message(message: dict, chat_id: int, admin_user_id=None) -> bool:
    from .models import TelegramBotDraft

    poster_id, poster_uid = _extract_photo_ids(message)
    if not poster_id:
        return False

    caption = message.get('caption') or ''
    meta = parse_movie_caption(caption)
    media_group_id = str(message.get('media_group_id') or '')

    draft = _get_or_create_draft(chat_id, media_group_id, admin_user_id)
    draft.poster_file_id = poster_id
    draft.poster_file_unique_id = poster_uid
    draft.caption = caption
    draft.metadata = _merge_metadata(draft.metadata, meta)
    draft.save()

    send_bot_message(
        chat_id,
        '🖼 Poster qabul qilindi.\n'
        f'📂 Bo\'lim: {meta.get("category", "filmy (default)")}\n'
        f'🎬 Nom: {meta.get("title", "—")}\n\n'
        'Endi video yuboring (poster xabariga reply qilsangiz ham bo\'ladi).',
    )
    return True


def _handle_video_message(message: dict, video_data: dict, chat_id: int, admin_user_id=None) -> bool:
    from .models import TelegramBotDraft

    tg_video, _ = save_telegram_video(video_data)

    caption = video_data.get('caption') or message.get('caption') or ''
    meta = parse_movie_caption(caption)

    poster_file_id = ''
    draft = None
    media_group_id = str(message.get('media_group_id') or '')

    reply = message.get('reply_to_message') or {}
    reply_photo_id, _ = _extract_photo_ids(reply)
    if reply_photo_id:
        poster_file_id = reply_photo_id
        if reply.get('caption'):
            meta = _merge_metadata(parse_movie_caption(reply.get('caption')), meta)

    if not poster_file_id and media_group_id:
        draft = TelegramBotDraft.objects.filter(
            chat_id=chat_id, media_group_id=media_group_id, is_complete=False,
        ).first()
        if draft and draft.poster_file_id:
            poster_file_id = draft.poster_file_id
            meta = _merge_metadata(draft.metadata, meta)

    if not poster_file_id:
        draft = TelegramBotDraft.objects.filter(
            chat_id=chat_id, is_complete=False, poster_file_id__gt='',
        ).order_by('-updated_at').first()
        if draft:
            poster_file_id = draft.poster_file_id
            meta = _merge_metadata(draft.metadata, meta)

    if not poster_file_id:
        poster_file_id = _video_thumb_file_id(message)

    if not meta.get('title') and caption:
        meta = _merge_metadata(parse_movie_caption(caption), meta)

    movie = create_movie_from_telegram(
        video_data=video_data,
        metadata=meta,
        poster_file_id=poster_file_id,
        tg_video_record=tg_video,
    )

    if movie:
        if draft:
            draft.is_complete = True
            draft.save(update_fields=['is_complete'])
        from django.urls import reverse
        path = reverse('movie:detail', kwargs={'slug': movie.slug})
        send_bot_message(
            chat_id,
            f'✅ Saytda film yaratildi!\n'
            f'🎬 {movie.title}\n'
            f'📂 {movie.category.name}\n'
            f'🔗 {_site_url(path)}',
        )
        return True

    send_bot_message(
        chat_id,
        '✅ Video saqlandi.\n'
        '⚠️ Saytda avtomatik yaratilmadi — poster yuboring (caption: nom + bo\'lim), '
        'keyin videoni reply qiling.\n'
        'Yoki admin panel → Telegram bo\'limidan bog\'lang.',
    )
    return True


def _handle_help(chat_id: int) -> None:
    from .telegram_bot_wizard import show_main_menu
    show_main_menu(chat_id)
