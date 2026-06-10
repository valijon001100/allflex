import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .models import Movie, MovieStream
from .utils import user_can_watch_movies


@login_required
def protected_stream(request, movie_id, quality):
    if not user_can_watch_movies(request.user):
        return HttpResponseForbidden()

    movie = get_object_or_404(Movie, pk=movie_id)
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
            return response
        if stream.url:
            return HttpResponseRedirect(stream.url)

    if quality == '720' and movie.video_url:
        return HttpResponseRedirect(movie.video_url)

    raise Http404()
