import mimetypes
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .models import Movie, MovieStream, PiracyAlert, UserProfile
from .utils import user_can_watch_movies


def _check_stream_referrer(request, movie):
    referer = request.META.get('HTTP_REFERER', '')
    if not referer:
        return
    host = urlparse(referer).netloc.lower().split(':')[0]
    allowed = {'localhost', '127.0.0.1', 'testserver'}
    for h in settings.ALLOWED_HOSTS:
        if h and h != '*':
            allowed.add(h.lower())
    if host and host not in allowed:
        profile = UserProfile.objects.filter(user=request.user).first()
        PiracyAlert.objects.create(
            movie=movie,
            detected_domain=host,
            detected_url=referer[:500],
            description=f'Shubhali referrer: {host}. Obunachi: {profile.subscriber_code if profile else "—"}',
            ip_address=request.META.get('REMOTE_ADDR'),
            notified_rights_holder=True,
        )


@login_required
def protected_stream(request, movie_id, quality):
    if not user_can_watch_movies(request.user):
        return HttpResponseForbidden()

    movie = get_object_or_404(Movie, pk=movie_id)
    _check_stream_referrer(request, movie)
    profile = UserProfile.objects.filter(user=request.user).first()
    stream = MovieStream.objects.filter(movie=movie, quality=quality).first()

    if stream:
        if stream.video_file:
            content_type, _ = mimetypes.guess_type(stream.video_file.name)
            response = FileResponse(
                stream.video_file.open('rb'),
                content_type=content_type or 'video/mp4',
            )
            response['Content-Disposition'] = 'inline'
            response['Cache-Control'] = 'no-store'
            if profile:
                response['X-Alflix-Viewer'] = profile.subscriber_code
            if movie.watermark_token:
                response['X-Alflix-Watermark'] = movie.watermark_token
            return response
        if stream.url:
            return HttpResponseRedirect(stream.url)

    if quality == '720' and movie.video_url:
        return HttpResponseRedirect(movie.video_url)

    raise Http404()
