import mimetypes
import os
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .models import Movie, MovieStream, PiracyAlert, UserProfile
from .utils import user_can_watch_movies


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


def _is_allowed_stream_request(request):
    host = _referer_host(request)
    if not host:
        return True
    return host in _allowed_referer_hosts()


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


def _apply_stream_security_headers(response):
    response['Content-Disposition'] = 'inline'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@login_required
def protected_stream(request, movie_id, quality):
    if not user_can_watch_movies(request.user):
        return HttpResponseForbidden()

    movie = get_object_or_404(Movie, pk=movie_id)
    if not _is_allowed_stream_request(request):
        _check_stream_referrer(request, movie)
        return HttpResponseForbidden('Videoni faqat sayt ichida ko\'rish mumkin.')
    profile = UserProfile.objects.filter(user=request.user).first()
    stream = MovieStream.objects.filter(movie=movie, quality=quality).first()

    if stream:
        if stream.video_file:
            content_type, _ = mimetypes.guess_type(stream.video_file.name)
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
            return _apply_stream_security_headers(response)
        if stream.url:
            return HttpResponseRedirect(stream.url)

    if quality == '720' and movie.video_url:
        return HttpResponseRedirect(movie.video_url)

    raise Http404()
