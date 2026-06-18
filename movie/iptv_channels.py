import re
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify

from .models import TvChannel
from .iptv_logos import resolve_logo_url

EXTINF_RE = re.compile(
    r'#EXTINF:-1\s+(?:tvg-id="(?P<tvg_id>[^"]*)")?\s*,(?P<name>.+)',
    re.IGNORECASE,
)


def default_uz_playlist_path():
    bundled = Path(settings.BASE_DIR) / 'movie' / 'data' / 'uz.m3u'
    if bundled.is_file():
        return bundled
    return Path(settings.BASE_DIR) / 'iptv-master' / 'streams' / 'uz.m3u'


def parse_m3u_file(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'M3U fayl topilmadi: {path}')

    entries = []
    pending = None
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line == '#EXTM3U':
            continue
        if line.startswith('#EXTINF'):
            match = EXTINF_RE.match(line)
            if not match:
                continue
            pending = {
                'tvg_id': (match.group('tvg_id') or '').strip(),
                'name': (match.group('name') or '').strip(),
            }
            continue
        if pending and not line.startswith('#'):
            pending['stream_url'] = line
            entries.append(pending)
            pending = None
    return entries


def _quality_from_name(name):
    if '(' in name and ')' in name:
        return name.rsplit('(', 1)[-1].rstrip(')').strip()
    return ''


def _display_name(name):
    return name.split('(', 1)[0].strip()


def _slug_for_entry(entry, used_slugs):
    tvg_id = entry.get('tvg_id', '')
    if tvg_id:
        base = slugify(tvg_id.replace('.', '-').replace('@', '-'))
    else:
        base = slugify(_display_name(entry['name']))
    if not base:
        base = 'kanal'
    slug = base
    n = 2
    while slug in used_slugs:
        slug = f'{base}-{n}'
        n += 1
    used_slugs.add(slug)
    return slug


def sync_tv_channels_from_m3u(path=None, replace=False):
    playlist_path = Path(path) if path else default_uz_playlist_path()
    entries = parse_m3u_file(playlist_path)
    if replace:
        TvChannel.objects.all().delete()

    used_slugs = set(TvChannel.objects.values_list('slug', flat=True))
    created = updated = 0

    for order, entry in enumerate(entries, start=1):
        name = entry['name']
        display_name = _display_name(name)
        quality = _quality_from_name(name)
        tvg_id = entry.get('tvg_id', '')
        stream_url = entry['stream_url']
        logo_url = resolve_logo_url(tvg_id)

        existing = None
        if tvg_id:
            existing = TvChannel.objects.filter(tvg_id=tvg_id, stream_url=stream_url).first()
        if not existing:
            existing = TvChannel.objects.filter(name=name, stream_url=stream_url).first()

        if existing:
            changed = False
            for field, value in (
                ('name', name),
                ('quality', quality),
                ('order', order),
                ('is_active', True),
                ('logo_url', logo_url),
            ):
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True
            if changed:
                existing.save()
                updated += 1
            continue

        slug = _slug_for_entry(entry, used_slugs)
        TvChannel.objects.create(
            name=name,
            slug=slug,
            tvg_id=tvg_id,
            stream_url=stream_url,
            quality=quality,
            logo_url=logo_url,
            order=order,
            is_active=True,
        )
        created += 1

    return {
        'path': str(playlist_path),
        'total': len(entries),
        'created': created,
        'updated': updated,
    }
