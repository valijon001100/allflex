from django.db import OperationalError
from django.db.models import Prefetch
from django.utils.translation import get_language
from .models import Category, Genre, TicketCategory
from .translations import translate_category
from .utils import user_can_watch_live, user_can_watch_movies, user_has_subscription

GENRE_NAV_ORDER = [
    'komediya', 'drama', 'tarixiy', 'semejnyj', 'hujjatli', 'uzhasy', 'musiqiy',
    'boevik', 'fantastika', 'fentezi', 'triller', 'priklyucheniya',
    'melodrama', 'kriminal', 'biografiya', 'sport', 'voennyj',
]


def _ordered_genres():
    order = {slug: idx for idx, slug in enumerate(GENRE_NAV_ORDER)}
    genres = list(Genre.objects.all())
    genres.sort(key=lambda genre: (order.get(genre.slug, 999), genre.name_uz or genre.name))
    return genres


def _nav_categories(lang):
    child_qs = Category.objects.filter(is_active=True).order_by('order', 'name')
    parents = Category.objects.filter(
        is_active=True, parent__isnull=True,
    ).prefetch_related(
        Prefetch('children', queryset=child_qs),
    ).order_by('order', 'name')
    return [
        {
            'obj': cat,
            'name': translate_category(cat, lang),
            'children': [
                {'obj': child, 'name': translate_category(child, lang)}
                for child in cat.children.all()
            ],
        }
        for cat in parents
    ]


def view_all(request):
    lang = get_language() or 'ru'
    categories = _nav_categories(lang)
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
        'genres': _ordered_genres(),
        'current_language': lang,
        'has_subscription': user_has_subscription(request.user),
        'has_movie_access': user_can_watch_movies(request.user),
        'has_live_access': user_can_watch_live(request.user),
    }
