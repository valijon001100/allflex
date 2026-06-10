from django.utils.translation import get_language
from .models import Category, Genre
from .translations import translate_category
from .utils import user_can_watch_live, user_can_watch_movies, user_has_subscription


def view_all(request):
    lang = get_language() or 'ru'
    categories = [
        {'obj': cat, 'name': translate_category(cat, lang)}
        for cat in Category.objects.filter(is_active=True, parent__isnull=True)
    ]
    return {
        'categories': categories,
        'genres': Genre.objects.all(),
        'current_language': lang,
        'has_subscription': user_has_subscription(request.user),
        'has_movie_access': user_can_watch_movies(request.user),
        'has_live_access': user_can_watch_live(request.user),
    }
