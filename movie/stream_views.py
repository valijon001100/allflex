import mimetypes
import os
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden, StreamingHttpResponse
from django.shortcuts import get_object_or_404

from .models import Movie, MovieStream, PiracyAlert, UserProfile
from .stream_utils import (
    DOWNLOAD_USER_AGENTS,
    iter_watermarked_video,
    log_watch_history,
    server_watermark_enabled,
    verify_stream_request,
    verify_trailer_request,
)
from .telegram_storage import TelegramStorageError, iter_telegram_stream
from .utils import get_movie_share_access, user_can_watch_movies


def _allowed_referer_hosts():
    allowed = {'localhost', '127.0.0.1', 'testserver'}
    for h in settings.ALLOWED_HOSTS:
        if h and h != '*':
            allowed.add(h.lower())
    render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip().lower()
    if render_host:
        allowed.add(render_host)
    return allowed


def _referer_host(request):
    referer = request.META.get('HTTP_REFERER', '')
    if not referer:
        return ''
    return urlparse(referer).netloc.lower().split(':')[0]


def _is_download_tool(request):
    ua = (request.META.get('HTTP_USER_AGENT') or '').lower()
    return any(marker in ua for marker in DOWNLOAD_USER_AGENTS)


def _is_embedded_playback(request):
    if _is_download_tool(request):
        return False
    dest = (request.META.get('HTTP_SEC_FETCH_DEST') or '').lower()
    if dest == 'document':
        return False
    if dest == 'video':
        return True
    ref = _referer_host(request)
    if ref and ref in _allowed_referer_hosts():
        return True
    return False


def _check_stream_referrer(request, movie):
    host = _referer_host(request)
    if not host or host in _allowed_referer_hosts():
        return
    profile = UserProfile.objects.filter(user=request.user).first()
    referer = request.META.get('HTTP_REFERER', '')
    PiracyAlert.objects.create(
        movie=movie,
        detected_domain=host,
        detected_url=referer[:500],
        description=f'Shubhali referrer: {host}. Obunachi: {profile.subscriber_code if profile else "—"}',
        ip_address=request.META.get('REMOTE_ADDR'),
        notified_rights_holder=True,
    )


def _apply_stream_security_headers(response, subscriber_code=''):
    if subscriber_code:
        response['Content-Disposition'] = f'inline; filename="alfix-{subscriber_code}.mp4"'
    else:
        response['Content-Disposition'] = 'inline'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    response['X-Download-Options'] = 'noopen'
    return response


def protected_stream(request, movie_id, quality):
    user = request.user if request.user.is_authenticated else None
    movie_obj = Movie.objects.filter(pk=movie_id).first()
    has_full = bool(user and user_can_watch_movies(user))
    share = get_movie_share_access(request, movie_obj) if not has_full else None
    has_share = share is not None and share.movie_id == int(movie_id)

    if not has_full and not has_share:
        return HttpResponseForbidden()

    verify_user_id = user.pk if has_full and user else 0
    if not verify_stream_request(request, movie_id, quality, verify_user_id):
        return HttpResponseForbidden('Stream havolasi yaroqsiz yoki muddati tugagan.')

    if not _is_embedded_playback(request):
        movie = Movie.objects.filter(pk=movie_id).first()
        if movie:
            _check_stream_referrer(request, movie)
        return HttpResponseForbidden('Videoni faqat sayt playeri orqali ko\'rish mumkin.')

    movie = get_object_or_404(Movie, pk=movie_id)
    profile = UserProfile.objects.filter(user=user).first() if has_full else None
    if has_full:
        log_watch_history(request, user, movie, profile)
    stream = MovieStream.objects.filter(movie=movie, quality=quality).first()
    code = profile.subscriber_code if profile else ''

    if stream:
        if stream.telegram_file_id:
            range_header = request.META.get('HTTP_RANGE', '')
            try:
                generator, tg_headers = iter_telegram_stream(
                    stream.telegram_file_id,
                    range_header=range_header,
                )
                status = 206 if range_header and tg_headers.get('Content-Range') else 200
                response = StreamingHttpResponse(
                    generator,
                    status=status,
                    content_type=tg_headers.get('Content-Type', 'video/mp4'),
                )
                for header, value in tg_headers.items():
                    response[header] = value
                if profile:
                    response['X-Alflix-Viewer'] = profile.subscriber_code
                if movie.watermark_token:
                    response['X-Alflix-Watermark'] = movie.watermark_token
                return _apply_stream_security_headers(response, code)
            except TelegramStorageError:
                pass

        if stream.video_file:
            content_type, _ = mimetypes.guess_type(stream.video_file.name)
            if server_watermark_enabled() and code:
                try:
                    file_path = stream.video_file.path
                except Exception:
                    file_path = None
                if file_path and os.path.isfile(file_path):
                    gen = iter_watermarked_video(file_path, code)
                    if gen:
                        response = StreamingHttpResponse(
                            gen(),
                            content_type=content_type or 'video/mp4',
                        )
                        if profile:
                            response['X-Alflix-Viewer'] = profile.subscriber_code
                        if movie.watermark_token:
                            response['X-Alflix-Watermark'] = movie.watermark_token
                        return _apply_stream_security_headers(response, code)
            response = FileResponse(
                stream.video_file.open('rb'),
                content_type=content_type or 'video/mp4',
                as_attachment=False,
            )
            response['Accept-Ranges'] = 'bytes'
            if stream.video_file.size:
                response['Content-Length'] = stream.video_file.size
            if profile:
                response['X-Alflix-Viewer'] = profile.subscriber_code
            if movie.watermark_token:
                response['X-Alflix-Watermark'] = movie.watermark_token
            return _apply_stream_security_headers(response, code)
        if stream.url:
            return HttpResponseForbidden(
                'Tashqi video havolasidan yuklab olish taqiqlangan. Admin panelda fayl yuklang.',
            )

    if quality == '720' and movie.video_url:
        return HttpResponseForbidden(
            'Tashqi video havolasidan yuklab olish taqiqlangan. Admin panelda fayl yuklang.',
        )

    raise Http404()


def public_trailer_stream(request, movie_id):
    if not verify_trailer_request(request, movie_id):
        return HttpResponseForbidden('Treler havolasi yaroqsiz yoki muddati tugagan.')

    if not _is_embedded_playback(request):
        return HttpResponseForbidden('Treilerni faqat sayt playeri orqali ko\'rish mumkin.')

    movie = get_object_or_404(Movie, pk=movie_id)
    if not movie.has_trailer():
        raise Http404()

    if movie.trailer_telegram_file_id:
        range_header = request.META.get('HTTP_RANGE', '')
        try:
            generator, tg_headers = iter_telegram_stream(
                movie.trailer_telegram_file_id,
                range_header=range_header,
            )
            status = 206 if range_header and tg_headers.get('Content-Range') else 200
            response = StreamingHttpResponse(
                generator,
                status=status,
                content_type=tg_headers.get('Content-Type', 'video/mp4'),
            )
            for header, value in tg_headers.items():
                response[header] = value
            return _apply_stream_security_headers(response)
        except TelegramStorageError:
            pass

    if movie.trailer_file:
        content_type, _ = mimetypes.guess_type(movie.trailer_file.name)
        response = FileResponse(
            movie.trailer_file.open('rb'),
            content_type=content_type or 'video/mp4',
            as_attachment=False,
        )
        response['Accept-Ranges'] = 'bytes'
        if movie.trailer_file.size:
            response['Content-Length'] = movie.trailer_file.size
        return _apply_stream_security_headers(response)

    if movie.trailer_url:
        return HttpResponseForbidden(
            'Tashqi treler havolasidan yuklab olish taqiqlangan. Admin panelda fayl yuklang.',
        )

    raise Http404()
