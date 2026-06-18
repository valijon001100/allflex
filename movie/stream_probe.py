from urllib.request import Request, urlopen

from .channel_stream import _upstream_headers

CINERAMA_HOST = 'cinerama.uz'


def is_cinerama_url(url):
    return CINERAMA_HOST in (url or '')


def probe_stream_url(url, timeout=8):
    if not url or is_cinerama_url(url):
        return False
    try:
        request = Request(url, headers=_upstream_headers(url))
        with urlopen(request, timeout=timeout) as response:
            sample = response.read(4096).decode('utf-8', errors='ignore')
        return '#EXTM3U' in sample or '#EXT-X-' in sample
    except Exception:
        return False
