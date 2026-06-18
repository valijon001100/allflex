import json
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from django.conf import settings

LOGOS_API_URL = 'https://iptv-org.github.io/api/logos.json'
RASTER_FORMATS = {'PNG', 'JPEG', 'WEBP', 'GIF', 'AVIF', 'APNG'}


def _logos_cache_path():
    return Path(settings.BASE_DIR) / 'movie' / 'data' / 'channel_logos.json'


def _build_logo_map(items):
    best = {}
    for item in items:
        channel = (item.get('channel') or '').strip()
        url = (item.get('url') or '').strip()
        if not channel or not url:
            continue
        fmt = (item.get('format') or '').upper()
        score = 0
        if item.get('in_use'):
            score += 100
        if fmt in RASTER_FORMATS:
            score += 20
        if fmt == 'SVG':
            score += 5
        score += min((item.get('width') or 0) // 50, 10)
        prev = best.get(channel)
        if prev is None or score > prev[0]:
            best[channel] = (score, url)
    return {channel: url for channel, (_, url) in best.items()}


def _fetch_logo_map_from_api():
    with urlopen(LOGOS_API_URL, timeout=60) as response:
        items = json.loads(response.read().decode('utf-8'))
    return _build_logo_map(items)


@lru_cache(maxsize=1)
def get_logo_map():
    cache_path = _logos_cache_path()
    if cache_path.is_file():
        try:
            data = json.loads(cache_path.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    try:
        return _fetch_logo_map_from_api()
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return {}


def resolve_logo_url(tvg_id):
    channel_id = (tvg_id or '').split('@', 1)[0].strip()
    if not channel_id:
        return ''
    return get_logo_map().get(channel_id, '')


def refresh_channel_logos(queryset=None):
    from .models import TvChannel

    logo_map = get_logo_map()
    if not logo_map:
        return 0

    channels = queryset if queryset is not None else TvChannel.objects.all()
    updated = 0
    for channel in channels.iterator():
        channel_id = (channel.tvg_id or '').split('@', 1)[0].strip()
        logo_url = logo_map.get(channel_id, '')
        if logo_url and channel.logo_url != logo_url:
            channel.logo_url = logo_url
            channel.save(update_fields=['logo_url'])
            updated += 1
    return updated


def download_logo_cache():
    logo_map = _fetch_logo_map_from_api()
    cache_path = _logos_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(logo_map, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
    get_logo_map.cache_clear()
    return len(logo_map)
