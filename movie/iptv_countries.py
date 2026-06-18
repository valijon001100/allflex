import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db.models import Count
from django.utils.translation import get_language

PRIMARY_COUNTRY = 'uz'
COUNTRIES_URL = 'https://iptv-org.github.io/iptv/countries/{code}.m3u'
PLAYLIST_URLS = (
    'https://iptv-org.github.io/iptv/countries/{code}.m3u',
    'https://raw.githubusercontent.com/iptv-org/iptv/master/streams/{code}.m3u',
)


def _data_dir():
    return Path(settings.BASE_DIR) / 'movie' / 'data'


@lru_cache(maxsize=1)
def get_country_codes():
    path = _data_dir() / 'country_codes.json'
    if path.is_file():
        codes = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(codes, list) and codes:
            return sorted_country_codes(codes)
    return [PRIMARY_COUNTRY]


@lru_cache(maxsize=1)
def get_countries_meta():
    path = _data_dir() / 'countries.json'
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return data
    return {}


def sorted_country_codes(codes):
    unique = sorted({code.lower() for code in codes if code})
    if PRIMARY_COUNTRY in unique:
        unique.remove(PRIMARY_COUNTRY)
        return [PRIMARY_COUNTRY] + unique
    return unique


def country_label(code, lang=None):
    lang = (lang or get_language() or 'uz').split('-')[0]
    meta = get_countries_meta().get(code.lower(), {})
    name = meta.get('name') or code.upper()
    flag = meta.get('flag') or country_flag(code)
    if lang == 'uz' and code == PRIMARY_COUNTRY:
        return "O'zbekiston"
    if lang == 'ru' and code == PRIMARY_COUNTRY:
        return 'Узбекистан'
    if lang == 'en' and code == PRIMARY_COUNTRY:
        return 'Uzbekistan'
    return name


def country_flag(code):
    code = (code or '').upper()
    if len(code) != 2 or not code.isalpha():
        return ''
    return ''.join(chr(0x1F1E6 + ord(char) - ord('A')) for char in code)


def country_nav_label(code, lang=None):
    flag = get_countries_meta().get(code.lower(), {}).get('flag') or country_flag(code)
    name = country_label(code, lang)
    return f'{flag} {name}'.strip()


def country_order_base(code):
    codes = get_country_codes()
    try:
        return codes.index(code.lower()) * 10000
    except ValueError:
        return len(codes) * 10000


def build_country_nav(queryset, lang=None, include_empty=True):
    counts = {
        row['country_code']: row['total']
        for row in queryset.values('country_code').annotate(total=Count('id'))
    }
    items = []
    for code in get_country_codes():
        total = counts.get(code, 0)
        if total or include_empty:
            items.append({
                'code': code,
                'label': country_nav_label(code, lang),
                'count': total,
                'loaded': total > 0,
            })
    for code, total in sorted(counts.items()):
        known = get_country_codes()
        if code not in known and total:
            items.append({
                'code': code,
                'label': country_nav_label(code, lang),
                'count': total,
                'loaded': True,
            })
    return items


POPULAR_COUNTRY_CODES = ('uz', 'ru', 'us', 'tr', 'kz', 'de', 'fr', 'gb', 'ua', 'in', 'cn', 'jp', 'kr')


def popular_country_nav(lang=None, queryset=None):
    counts = {}
    if queryset is not None:
        counts = {
            row['country_code']: row['total']
            for row in queryset.values('country_code').annotate(total=Count('id'))
        }
    return [
        {
            'code': code,
            'label': country_nav_label(code, lang),
            'count': counts.get(code, 0),
            'loaded': counts.get(code, 0) > 0,
        }
        for code in POPULAR_COUNTRY_CODES
        if code in get_country_codes() or code == PRIMARY_COUNTRY
    ]
