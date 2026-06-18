from pathlib import Path

from django.conf import settings
from django.db import migrations
from django.utils.text import slugify

import re

EXTINF_RE = re.compile(
    r'#EXTINF:-1\s+(?:tvg-id="(?P<tvg_id>[^"]*)")?\s*,(?P<name>.+)',
    re.IGNORECASE,
)


def _parse_m3u(path):
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


def _slug_for_entry(entry, used_slugs):
    tvg_id = entry.get('tvg_id', '')
    if tvg_id:
        base = slugify(tvg_id.replace('.', '-').replace('@', '-'))
    else:
        base = slugify(entry['name'].split('(', 1)[0].strip())
    if not base:
        base = 'kanal'
    slug = base
    n = 2
    while slug in used_slugs:
        slug = f'{base}-{n}'
        n += 1
    used_slugs.add(slug)
    return slug


def load_tv_channels(apps, schema_editor):
    TvChannel = apps.get_model('movie', 'TvChannel')
    if TvChannel.objects.exists():
        return

    playlist = Path(settings.BASE_DIR) / 'movie' / 'data' / 'uz.m3u'
    if not playlist.is_file():
        return

    used_slugs = set()
    for order, entry in enumerate(_parse_m3u(playlist), start=1):
        name = entry['name']
        TvChannel.objects.create(
            name=name,
            slug=_slug_for_entry(entry, used_slugs),
            tvg_id=entry.get('tvg_id', ''),
            stream_url=entry['stream_url'],
            quality=_quality_from_name(name),
            order=order,
            is_active=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0035_tvchannel'),
    ]

    operations = [
        migrations.RunPython(load_tv_channels, migrations.RunPython.noop),
    ]
