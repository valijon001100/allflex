from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import TvChannel

IPTV_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
)


def _fetch_upstream(url, timeout=25):
    request = Request(url, headers={
        'User-Agent': IPTV_USER_AGENT,
        'Accept': '*/*',
    })
    return urlopen(request, timeout=timeout)


def _rewrite_playlist(body, source_url, segment_proxy_url):
    base = source_url.rsplit('/', 1)[0] + '/'
    output = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            output.append(line)
            continue
        if stripped.startswith('#'):
            output.append(line)
            continue
        absolute = urljoin(base, stripped)
        output.append(f'{segment_proxy_url}?u={quote(absolute, safe="")}')
    return '\n'.join(output) + '\n'


@require_GET
def channel_playlist(request, slug):
    channel = get_object_or_404(TvChannel, slug=slug, is_active=True)
    source_url = channel.stream_url
    if not source_url:
        return HttpResponseBadRequest('Stream URL yo\'q')

    try:
        with _fetch_upstream(source_url) as upstream:
            body = upstream.read().decode('utf-8', errors='replace')
            raw_content_type = upstream.headers.get('Content-Type', 'application/octet-stream')
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return HttpResponse(f'#EXTM3U\n# ERROR: {exc}', content_type='text/plain', status=502)

    segment_proxy = request.build_absolute_uri(
        f'/telekanallar/{slug}/segment/'
    )
    if '.m3u8' in source_url.lower() or '#EXTM3U' in body:
        body = _rewrite_playlist(body, source_url, segment_proxy)
        content_type = 'application/vnd.apple.mpegurl'
    else:
        content_type = raw_content_type

    response = HttpResponse(body, content_type=content_type)
    response['Cache-Control'] = 'no-cache'
    response['Access-Control-Allow-Origin'] = '*'
    return response


@require_GET
def channel_segment(request, slug):
    get_object_or_404(TvChannel, slug=slug, is_active=True)
    target = request.GET.get('u', '').strip()
    if not target or not target.startswith(('http://', 'https://')):
        return HttpResponseBadRequest('Noto\'g\'ri URL')

    parsed = urlparse(target)
    if parsed.scheme not in ('http', 'https'):
        return HttpResponseBadRequest('Noto\'g\'ri URL')

    try:
        upstream = _fetch_upstream(target)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return HttpResponse(str(exc), status=502)

    content_type = upstream.headers.get('Content-Type', 'application/octet-stream')
    if target.endswith('.m3u8') or 'mpegurl' in content_type.lower():
        body = upstream.read().decode('utf-8', errors='replace')
        segment_proxy = request.build_absolute_uri(
            f'/telekanallar/{slug}/segment/'
        )
        body = _rewrite_playlist(body, target, segment_proxy)
        response = HttpResponse(body, content_type='application/vnd.apple.mpegurl')
        response['Cache-Control'] = 'no-cache'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def stream():
        try:
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            upstream.close()

    response = StreamingHttpResponse(stream(), content_type=content_type)
    response['Cache-Control'] = 'no-cache'
    response['Access-Control-Allow-Origin'] = '*'
    return response
