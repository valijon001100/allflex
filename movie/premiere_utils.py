from django.utils.translation import get_language

from .models import HomePremiere, Movie, SiteSettings


def get_home_premiere_context():
    settings = SiteSettings.load()
    lang = get_language() or 'uz'

    if not settings.premiere_enabled:
        return {
            'premiere_movies': [],
            'premiere_settings': settings,
            'premiere_title': settings.get_premiere_title(lang),
            'premiere_rotate_seconds': settings.premiere_rotate_seconds,
        }

    limit = max(1, min(int(settings.premiere_slides_count or 5), 20))
    slots = list(
        HomePremiere.objects.filter(is_active=True)
        .select_related('movie', 'movie__category')
        .order_by('order', 'id')[:limit]
    )
    movies = [slot.movie for slot in slots if slot.movie.poster and slot.movie.poster.name]

    if len(movies) < limit:
        used_ids = {movie.pk for movie in movies}
        extras = (
            Movie.objects.exclude(poster='')
            .exclude(pk__in=used_ids)
            .select_related('category')
            .order_by('-created_at', '-id')[: limit - len(movies)]
        )
        movies.extend(list(extras))

    return {
        'premiere_movies': movies[:limit],
        'premiere_settings': settings,
        'premiere_title': settings.get_premiere_title(lang),
        'premiere_rotate_seconds': max(3, min(int(settings.premiere_rotate_seconds or 6), 60)),
    }
