import re
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from django.conf import settings
from django.utils.text import slugify

from .iptv_countries import (
    PRIMARY_COUNTRY,
    PLAYLIST_URLS,
    country_order_base,
    get_country_codes,
)
from .iptv_logos import resolve_logo_url
from .models import TvChannel

EXTINF_RE = re.compile(
    r'#EXTINF:-1\s+(?:tvg-id="(?P<tvg_id>[^"]*)")?\s*,(?P<name>.+)',
    re.IGNORECASE,
)


def _streams_dir():
    return Path(settings.BASE_DIR) / 'iptv-master' / 'streams'


def default_uz_playlist_path():
    bundled = Path(settings.BASE_DIR) / 'movie' / 'data' / 'uz.m3u'
    if bundled.is_file():
        return bundled
    return _streams_dir() / 'uz.m3u'


def parse_m3u_content(text):
    entries = []
    pending = None
    for raw_line in text.splitlines():
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


def parse_m3u_file(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'M3U fayl topilmadi: {path}')
    return parse_m3u_content(path.read_text(encoding='utf-8'))


def fetch_country_playlist(country_code):
    country_code = country_code.lower()
    local_path = _streams_dir() / f'{country_code}.m3u'
    if local_path.is_file():
        return parse_m3u_file(local_path)

    bundled = Path(settings.BASE_DIR) / 'movie' / 'data' / f'{country_code}.m3u'
    if bundled.is_file():
        return parse_m3u_file(bundled)

    last_error = None
    for template in PLAYLIST_URLS:
        url = template.format(code=country_code)
        try:
            with urlopen(url, timeout=30) as response:
                content = response.read().decode('utf-8', errors='replace')
            entries = parse_m3u_content(content)
            if entries:
                return entries
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
    if last_error:
        raise FileNotFoundError(f'{country_code}.m3u topilmadi: {last_error}')
    return []


def _quality_from_name(name):
    if '(' in name and ')' in name:
        return name.rsplit('(', 1)[-1].rstrip(')').strip()
    return ''


def _slug_for_entry(entry, country_code, used_slugs):
    tvg_id = entry.get('tvg_id', '')
    if tvg_id:
        base = slugify(tvg_id.replace('.', '-').replace('@', '-'))
    else:
        base = slugify(entry['name'].split('(', 1)[0].strip())
    if not base:
        base = 'kanal'
    slug = f'{country_code}-{base}'
    counter = 2
    while slug in used_slugs:
        slug = f'{country_code}-{base}-{counter}'
        counter += 1
    used_slugs.add(slug)
    return slug


def _find_existing(country_code, tvg_id, name, stream_url):
    qs = TvChannel.objects.filter(country_code=country_code, stream_url=stream_url)
    if tvg_id:
        match = qs.filter(tvg_id=tvg_id).first()
        if match:
            return match
    return qs.filter(name=name).first()


def sync_country_channels(country_code, entries=None, replace_country=False, used_slugs=None):
    country_code = country_code.lower()
    if entries is None:
        entries = fetch_country_playlist(country_code)
    if replace_country:
        TvChannel.objects.filter(country_code=country_code).delete()

    used_slugs = set(used_slugs or TvChannel.objects.values_list('slug', flat=True))
    order_base = country_order_base(country_code)
    created = updated = 0

    for index, entry in enumerate(entries, start=1):
        name = entry['name']
        quality = _quality_from_name(name)
        tvg_id = entry.get('tvg_id', '')
        stream_url = entry['stream_url']
        logo_url = resolve_logo_url(tvg_id)
        order = order_base + index

        existing = _find_existing(country_code, tvg_id, name, stream_url)
        if existing:
            changed_fields = []
            for field, value in (
                ('name', name),
                ('quality', quality),
                ('order', order),
                ('is_active', True),
                ('logo_url', logo_url),
                ('country_code', country_code),
            ):
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed_fields.append(field)
            if changed_fields:
                existing.save(update_fields=changed_fields)
                updated += 1
            used_slugs.add(existing.slug)
            continue

        slug = _slug_for_entry(entry, country_code, used_slugs)
        TvChannel.objects.create(
            name=name,
            slug=slug,
            country_code=country_code,
            tvg_id=tvg_id,
            stream_url=stream_url,
            quality=quality,
            logo_url=logo_url,
            order=order,
            is_active=True,
        )
        created += 1

    return {
        'country_code': country_code,
        'total': len(entries),
        'created': created,
        'updated': updated,
    }


def sync_tv_channels_from_m3u(path=None, replace=False, country_code=PRIMARY_COUNTRY):
    if path:
        entries = parse_m3u_file(path)
        if replace:
            TvChannel.objects.all().delete()
        return sync_country_channels(country_code, entries=entries, replace_country=False)

    return sync_country_channels(country_code, entries=fetch_country_playlist(country_code))


def sync_all_tv_channels(replace=False, country_codes=None):
    if replace:
        TvChannel.objects.all().delete()
        codes = list(country_codes or get_country_codes())
    else:
        requested = list(country_codes or get_country_codes())
        loaded = set(
            TvChannel.objects.values_list('country_code', flat=True).distinct()
        )
        codes = [code for code in requested if code not in loaded]
        if not codes:
            return {
                'countries': 0,
                'total': 0,
                'created': 0,
                'updated': 0,
                'failed': [],
                'skipped': True,
            }

    used_slugs = set() if replace else set(TvChannel.objects.values_list('slug', flat=True))
    summary = {
        'countries': 0,
        'total': 0,
        'created': 0,
        'updated': 0,
        'failed': [],
    }

    for country_code in codes:
        try:
            result = sync_country_channels(
                country_code,
                replace_country=False,
                used_slugs=used_slugs,
            )
        except (FileNotFoundError, OSError) as exc:
            summary['failed'].append({'country': country_code, 'error': str(exc)})
            continue

        summary['countries'] += 1
        summary['total'] += result['total']
        summary['created'] += result['created']
        summary['updated'] += result['updated']

    return summary
