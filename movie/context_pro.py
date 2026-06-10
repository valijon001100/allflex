from django.db import OperationalError
from django.utils.translation import get_language
from .models import Category, Genre, TicketCategory
from .translations import translate_category
from .utils import user_can_watch_live, user_can_watch_movies, user_has_subscription


def view_all(request):
    lang = get_language() or 'ru'
    categories = [
        {'obj': cat, 'name': translate_category(cat, lang)}
        for cat in Category.objects.filter(is_active=True, parent__isnull=True)
    ]
    try:
        ticket_categories = [
            {'obj': cat, 'name': cat.get_translated_name(lang)}
            for cat in TicketCategory.objects.filter(is_active=True)
        ]
    except OperationalError:
        ticket_categories = []
    return {
        'categories': categories,
        'ticket_categories': ticket_categories,
        'genres': Genre.objects.all(),
        'current_language': lang,
        'has_subscription': user_has_subscription(request.user),
        'has_movie_access': user_can_watch_movies(request.user),
        'has_live_access': user_can_watch_live(request.user),
    }
