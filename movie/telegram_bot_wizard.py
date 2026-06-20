"""Telegram bot — bosqichma-bosqich film yuklash (inline tugmalar)."""
import logging
from typing import Optional

from django.urls import reverse
from django.utils import timezone

from .models import Category, TelegramBotDraft
from .telegram_movie_import import (
    _extract_photo_ids,
    _site_url,
    _video_thumb_file_id,
    create_movie_from_telegram,
    extract_channel_video,
    extract_video_from_message,
    parse_movie_caption,
)
from .telegram_storage import (
    answer_callback_query,
    is_telegram_admin,
    save_telegram_video,
    send_bot_message,
)

logger = logging.getLogger(__name__)

CANCEL_BTN = {'text': '❌ Bekor qilish', 'callback_data': 'wiz:cancel'}


def _command_name(text: str) -> str:
    token = (text or '').strip().split()[0] if text else ''
    if '@' in token:
        token = token.split('@', 1)[0]
    return token.lower()


def _inline(rows):
    return {'inline_keyboard': rows}


def _main_menu_keyboard():
    return _inline([
        [{'text': '🎬 Film qo\'shish', 'callback_data': 'wiz:start'}],
        [{'text': '📋 Yordam', 'callback_data': 'wiz:help'}],
    ])


def _category_keyboard():
    rows = []
    row = []
    cats = Category.objects.filter(is_active=True).select_related('parent').order_by(
        'parent__order', 'parent__name', 'order', 'name',
    )[:14]
    for cat in cats:
        label = cat.name_uz or cat.name
        if cat.parent_id:
            label = f'└ {label}'
        row.append({'text': label[:28], 'callback_data': f'wiz:cat:{cat.slug}'})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([CANCEL_BTN])
    return _inline(rows)


def _year_keyboard():
    current = timezone.now().year
    years = [str(current - 1), str(current), str(current + 1)]
    return _inline([
        [{'text': y, 'callback_data': f'wiz:year:{y}'} for y in years],
        [CANCEL_BTN],
    ])


def _quality_keyboard():
    return _inline([
        [
            {'text': '480p', 'callback_data': 'wiz:q:480'},
            {'text': '720p', 'callback_data': 'wiz:q:720'},
            {'text': '1080p', 'callback_data': 'wiz:q:1080'},
        ],
        [
            {'text': '4K', 'callback_data': 'wiz:q:4k'},
            {'text': '🎞 Treler', 'callback_data': 'wiz:q:trailer'},
        ],
        [CANCEL_BTN],
    ])


def _description_keyboard():
    return _inline([
        [{'text': '⏭ O\'tkazib yuborish', 'callback_data': 'wiz:skip:desc'}],
        [CANCEL_BTN],
    ])


def _confirm_keyboard():
    return _inline([
        [
            {'text': '✅ Saqlash', 'callback_data': 'wiz:save'},
            {'text': '❌ Bekor', 'callback_data': 'wiz:cancel'},
        ],
    ])


def _get_active_draft(chat_id: int) -> Optional[TelegramBotDraft]:
    return TelegramBotDraft.objects.filter(
        chat_id=chat_id, is_complete=False,
    ).exclude(step='').order_by('-updated_at').first()


def _cancel_draft(chat_id: int) -> None:
    TelegramBotDraft.objects.filter(chat_id=chat_id, is_complete=False).update(
        is_complete=True, step='',
    )


def _start_wizard(chat_id: int, admin_user_id: int) -> TelegramBotDraft:
    _cancel_draft(chat_id)
    return TelegramBotDraft.objects.create(
        chat_id=chat_id,
        admin_user_id=admin_user_id,
        step=TelegramBotDraft.STEP_TITLE,
        metadata={},
    )


def _step_prompt(draft: TelegramBotDraft) -> tuple:
    meta = draft.metadata or {}
    if draft.step == TelegramBotDraft.STEP_TITLE:
        return (
            '📝 1/7 — Film nomi\n\nFilm nomini yozing (masalan: Inception):',
            _inline([[CANCEL_BTN]]),
        )
    if draft.step == TelegramBotDraft.STEP_CATEGORY:
        return (
            f'📂 2/7 — Bo\'lim\n\n🎬 Nom: {meta.get("title", "—")}\n\nBo\'limni tanlang:',
            _category_keyboard(),
        )
    if draft.step == TelegramBotDraft.STEP_YEAR:
        return (
            '📅 3/7 — Yil\n\nYilni yozing yoki tugmani bosing:',
            _year_keyboard(),
        )
    if draft.step == TelegramBotDraft.STEP_DESCRIPTION:
        return (
            '📄 4/7 — Tavsif\n\nFilm haqida qisqacha yozing\n(yoki «O\'tkazib yuborish»):',
            _description_keyboard(),
        )
    if draft.step == TelegramBotDraft.STEP_QUALITY:
        return (
            '📊 5/7 — Video sifati\n\nSifatni tanlang:',
            _quality_keyboard(),
        )
    if draft.step == TelegramBotDraft.STEP_POSTER:
        return (
            '🖼 6/7 — Poster\n\nPoster rasmini yuboring (jpg/png):',
            _inline([[CANCEL_BTN]]),
        )
    if draft.step == TelegramBotDraft.STEP_VIDEO:
        q = meta.get('quality', '720')
        kind = 'Treler' if meta.get('type') == 'trailer' else f'{q}p video'
        return (
            f'🎥 7/7 — {kind}\n\nVideo faylni yuboring:',
            _inline([[CANCEL_BTN]]),
        )
    return ('', _main_menu_keyboard())


def _summary_text(draft: TelegramBotDraft) -> str:
    meta = draft.metadata or {}
    q = meta.get('quality', '720')
    kind = 'Treler' if meta.get('type') == 'trailer' else f'{q}p'
    return (
        '📋 Tekshirish\n\n'
        f'🎬 Nom: {meta.get("title", "—")}\n'
        f'📂 Bo\'lim: {meta.get("category_label", meta.get("category", "—"))}\n'
        f'📅 Yil: {meta.get("year", "—")}\n'
        f'📄 Tavsif: {(meta.get("description") or "—")[:120]}\n'
        f'📊 Sifat: {kind}\n'
        f'🖼 Poster: {"✅" if draft.poster_file_id else "❌"}\n'
        f'🎥 Video: {"✅" if draft.video_file_id else "❌"}\n\n'
        'Hammasi to\'g\'ri bo\'lsa «Saqlash» bosing:'
    )


def show_main_menu(chat_id: int, text: str = '') -> None:
    msg = text or '🎬 AL-FLIX bot\n\nFilm yuklash uchun tugmani bosing:'
    send_bot_message(chat_id, msg, reply_markup=_main_menu_keyboard())


def _advance_and_prompt(draft: TelegramBotDraft, chat_id: int) -> None:
    text, keyboard = _step_prompt(draft)
    send_bot_message(chat_id, text, reply_markup=keyboard)


def _set_step(draft: TelegramBotDraft, step: str, chat_id: int) -> None:
    draft.step = step
    draft.save(update_fields=['step', 'updated_at'])
    _advance_and_prompt(draft, chat_id)


def _finalize_draft(draft: TelegramBotDraft, chat_id: int) -> bool:
    meta = dict(draft.metadata or {})
    if not draft.video_file_id or not draft.poster_file_id:
        send_bot_message(chat_id, '⚠️ Poster va video kerak.', reply_markup=_confirm_keyboard())
        return False

    video_data = {
        'channel_id': chat_id,
        'message_id': 0,
        'file_id': draft.video_file_id,
        'file_unique_id': draft.video_file_unique_id,
        'file_name': meta.get('title', 'video'),
        'caption': meta.get('description', ''),
    }
    tg_video, _ = save_telegram_video(video_data)
    movie = create_movie_from_telegram(
        video_data=video_data,
        metadata=meta,
        poster_file_id=draft.poster_file_id,
        tg_video_record=tg_video,
    )
    draft.is_complete = True
    draft.step = ''
    draft.save(update_fields=['is_complete', 'step', 'updated_at'])

    if movie:
        path = reverse('movie:detail', kwargs={'slug': movie.slug})
        send_bot_message(
            chat_id,
            f'✅ Saytda yaratildi!\n\n'
            f'🎬 {movie.title}\n'
            f'📂 {movie.category.name}\n'
            f'🔗 {_site_url(path)}',
            reply_markup=_main_menu_keyboard(),
        )
        return True

    send_bot_message(chat_id, '❌ Saqlashda xato. Admin paneldan tekshiring.', reply_markup=_main_menu_keyboard())
    return False


def handle_callback(callback: dict) -> bool:
    user = callback.get('from') or {}
    if not is_telegram_admin(user.get('id')):
        return False

    chat_id = (callback.get('message') or {}).get('chat', {}).get('id')
    if not chat_id:
        return False

    data = (callback.get('data') or '').strip()
    answer_callback_query(callback.get('id', ''), '')

    if data == 'wiz:menu':
        _cancel_draft(chat_id)
        show_main_menu(chat_id)
        return True

    if data == 'wiz:help':
        send_bot_message(
            chat_id,
            '📋 Yordam\n\n'
            '1. «Film qo\'shish» tugmasi\n'
            '2. Nom → Bo\'lim → Yil → Tavsif\n'
            '3. Sifat → Poster → Video\n'
            '4. «Saqlash»',
            reply_markup=_main_menu_keyboard(),
        )
        return True

    if data == 'wiz:cancel':
        _cancel_draft(chat_id)
        send_bot_message(chat_id, '❌ Bekor qilindi.', reply_markup=_main_menu_keyboard())
        return True

    if data == 'wiz:start':
        draft = _start_wizard(chat_id, user.get('id'))
        _advance_and_prompt(draft, chat_id)
        return True

    draft = _get_active_draft(chat_id)

    if data.startswith('wiz:cat:') and draft:
        slug = data.split(':', 2)[2]
        cat = Category.objects.filter(slug=slug).first()
        meta = dict(draft.metadata or {})
        meta['category'] = slug
        meta['category_label'] = (cat.name_uz or cat.name) if cat else slug
        draft.metadata = meta
        draft.save(update_fields=['metadata', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_YEAR, chat_id)
        return True

    if data.startswith('wiz:year:') and draft:
        year = data.split(':', 2)[2]
        meta = dict(draft.metadata or {})
        meta['year'] = year
        draft.metadata = meta
        draft.save(update_fields=['metadata', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_DESCRIPTION, chat_id)
        return True

    if data == 'wiz:skip:desc' and draft and draft.step == TelegramBotDraft.STEP_DESCRIPTION:
        meta = dict(draft.metadata or {})
        meta.setdefault('description', meta.get('title', ''))
        draft.metadata = meta
        draft.save(update_fields=['metadata', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_QUALITY, chat_id)
        return True

    if data.startswith('wiz:q:') and draft:
        q = data.split(':', 2)[2]
        meta = dict(draft.metadata or {})
        if q == 'trailer':
            meta['type'] = 'trailer'
            meta['quality'] = '720'
        else:
            meta.pop('type', None)
            meta['quality'] = q
        draft.metadata = meta
        draft.save(update_fields=['metadata', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_POSTER, chat_id)
        return True

    if data == 'wiz:save' and draft and draft.step == TelegramBotDraft.STEP_CONFIRM:
        return _finalize_draft(draft, chat_id)

    send_bot_message(chat_id, '⚠️ Amal bajarilmadi. Bosh menyudan qayta boshlang.', reply_markup=_main_menu_keyboard())
    return True


def handle_wizard_message(message: dict, draft: TelegramBotDraft) -> bool:
    chat_id = (message.get('chat') or {}).get('id')
    text = (message.get('text') or '').strip()

    if draft.step == TelegramBotDraft.STEP_TITLE:
        if not text or text.startswith('/'):
            send_bot_message(chat_id, '⚠️ Film nomini matn ko\'rinishida yozing.', reply_markup=_inline([[CANCEL_BTN]]))
            return True
        meta = dict(draft.metadata or {})
        meta['title'] = text[:250]
        draft.metadata = meta
        draft.save(update_fields=['metadata', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_CATEGORY, chat_id)
        return True

    if draft.step == TelegramBotDraft.STEP_YEAR:
        if not text or not text.isdigit() or len(text) != 4:
            send_bot_message(chat_id, '⚠️ To\'g\'ri yil yozing (masalan 2024) yoki tugmani bosing.', reply_markup=_year_keyboard())
            return True
        meta = dict(draft.metadata or {})
        meta['year'] = text
        draft.metadata = meta
        draft.save(update_fields=['metadata', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_DESCRIPTION, chat_id)
        return True

    if draft.step == TelegramBotDraft.STEP_DESCRIPTION:
        if not text:
            send_bot_message(chat_id, '⚠️ Tavsif yozing yoki «O\'tkazib yuborish» bosing.', reply_markup=_description_keyboard())
            return True
        meta = dict(draft.metadata or {})
        meta['description'] = text[:2000]
        draft.metadata = meta
        draft.save(update_fields=['metadata', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_QUALITY, chat_id)
        return True

    if draft.step == TelegramBotDraft.STEP_POSTER:
        photo_id, photo_uid = _extract_photo_ids(message)
        if not photo_id:
            send_bot_message(chat_id, '🖼 Poster rasm yuboring (jpg/png).', reply_markup=_inline([[CANCEL_BTN]]))
            return True
        draft.poster_file_id = photo_id
        draft.poster_file_unique_id = photo_uid
        draft.save(update_fields=['poster_file_id', 'poster_file_unique_id', 'updated_at'])
        _set_step(draft, TelegramBotDraft.STEP_VIDEO, chat_id)
        return True

    if draft.step == TelegramBotDraft.STEP_VIDEO:
        media = extract_video_from_message(message)
        if not media:
            send_bot_message(chat_id, '🎥 Video fayl yuboring (.mp4, .mkv...).', reply_markup=_inline([[CANCEL_BTN]]))
            return True
        draft.video_file_id = media['file_id']
        draft.video_file_unique_id = media['file_unique_id']
        draft.save(update_fields=['video_file_id', 'video_file_unique_id', 'updated_at'])
        draft.step = TelegramBotDraft.STEP_CONFIRM
        draft.save(update_fields=['step', 'updated_at'])
        send_bot_message(chat_id, _summary_text(draft), reply_markup=_confirm_keyboard())
        return True

    text, keyboard = _step_prompt(draft)
    send_bot_message(chat_id, text or 'Davom eting:', reply_markup=keyboard)
    return True


def handle_channel_update(update: dict) -> bool:
    message = update.get('channel_post') or update.get('edited_channel_post')
    if not message:
        return False

    video_data = extract_channel_video(update)
    if not video_data:
        return False

    tg_video, _ = save_telegram_video(video_data)
    meta = parse_movie_caption(video_data.get('caption', ''))
    poster_file_id = _video_thumb_file_id(message)
    movie = create_movie_from_telegram(
        video_data=video_data,
        metadata=meta,
        poster_file_id=poster_file_id,
        tg_video_record=tg_video,
    )
    return bool(movie)


def handle_telegram_update(update: dict) -> bool:
    try:
        return _handle_telegram_update(update)
    except Exception:
        logger.exception('Telegram wizard xatosi')
        message = update.get('message') or (update.get('callback_query') or {}).get('message')
        user = (update.get('message') or {}).get('from') or (update.get('callback_query') or {}).get('from') or {}
        chat_id = (message or {}).get('chat', {}).get('id')
        if chat_id and is_telegram_admin(user.get('id')):
            send_bot_message(
                chat_id,
                '⚠️ Xatolik yuz berdi. `python manage.py migrate` va redeploy qiling.',
                reply_markup=_main_menu_keyboard(),
            )
        return False


def _handle_telegram_update(update: dict) -> bool:
    if 'callback_query' in update:
        return handle_callback(update['callback_query'])

    message = (
        update.get('message')
        or update.get('edited_message')
        or update.get('channel_post')
        or update.get('edited_channel_post')
    )
    if not message:
        return False

    if update.get('channel_post') or update.get('edited_channel_post'):
        return handle_channel_update(update)

    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    user = message.get('from') or {}
    if not is_telegram_admin(user.get('id')):
        return False

    text = (message.get('text') or '').strip()
    command = _command_name(text)
    if command in ('/start', '/help', '/yordam'):
        _cancel_draft(chat_id)
        show_main_menu(chat_id)
        return True

    draft = _get_active_draft(chat_id)
    if draft:
        return handle_wizard_message(message, draft)

    if extract_video_from_message(message):
        send_bot_message(
            chat_id,
            'ℹ️ Avval «Film qo\'shish» tugmasini bosing — ma\'lumotlar bosqichma-bosqich so\'raladi.',
            reply_markup=_main_menu_keyboard(),
        )
        return True

    show_main_menu(chat_id)
    return True
