from django.db import OperationalError
from django.db.models import Prefetch
from django.urls import reverse
from django.utils.translation import get_language
from .models import Category, Genre, TicketCategory
from .translations import translate_category
from .utils import user_can_watch_live, user_can_watch_movies, user_has_subscription

GENRE_NAV_ORDER = [
    'komediya', 'drama', 'tarixiy', 'semejnyj', 'hujjatli', 'uzhasy', 'musiqiy',
    'boevik', 'fantastika', 'fentezi', 'triller', 'priklyucheniya',
    'melodrama', 'kriminal', 'biografiya', 'sport', 'voennyj',
]

DEFAULT_TICKET_NAV = [
    {'slug': 'kino', 'name_uz': 'Kinoteatr', 'name_ru': 'Кинотеатр', 'name_en': 'Cinema', 'icon': '🎬'},
    {'slug': 'teatr', 'name_uz': 'Teatr', 'name_ru': 'Театр', 'name_en': 'Theater', 'icon': '🎭'},
    {'slug': 'sirk', 'name_uz': 'Sirk', 'name_ru': 'Цирк', 'name_en': 'Circus', 'icon': '🎪'},
]

KINOTEATR_NAV_SAMPLES = [
    {'slug': 'avatar-3-premyera', 'name_uz': 'Avatar 3 — Premyera', 'name_ru': 'Avatar 3 — Премьера', 'name_en': 'Avatar 3 — Premiere'},
    {'slug': 'uzbek-kino-kechasi', 'name_uz': "O'zbek kino kechasi", 'name_ru': 'Узбекский кино вечер', 'name_en': 'Uzbek Cinema Night'},
]


def _localized_name(data, lang):
    if lang and lang.startswith('en'):
        return data.get('name_en') or data.get('name_uz')
    if lang and lang.startswith('ru'):
        return data.get('name_ru') or data.get('name_uz')
    return data.get('name_uz') or data.get('name_ru')


def _ordered_genres():
    order = {slug: idx for idx, slug in enumerate(GENRE_NAV_ORDER)}
    try:
        genres = list(Genre.objects.all())
    except OperationalError:
        return []
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


def _ticket_nav(lang):
    try:
        db_cats = {c.slug: c for c in TicketCategory.objects.filter(is_active=True)}
    except OperationalError:
        db_cats = {}
    items = []
    for spec in DEFAULT_TICKET_NAV:
        cat = db_cats.get(spec['slug'])
        if cat:
            items.append({
                'name': cat.get_translated_name(lang),
                'url': cat.get_absolute_url(),
                'icon': cat.icon or spec['icon'],
            })
        else:
            items.append({
                'name': _localized_name(spec, lang),
                'url': reverse('movie:ticket_category', kwargs={'slug': spec['slug']}),
                'icon': spec['icon'],
            })
    return items


def _kinoteatr_nav(lang):
    labels = {'uz': 'Kinoteatr', 'ru': 'Кинотеатр', 'en': 'Cinema'}
    code = (lang or 'uz')[:2]
    return {
        'label': labels.get(code, labels['uz']),
        'home_url': reverse('movie:ticket_category', kwargs={'slug': 'kino'}),
        'samples': [
            {
                'name': _localized_name(spec, lang),
                'url': reverse('movie:ticket_detail', kwargs={'slug': spec['slug']}),
            }
            for spec in KINOTEATR_NAV_SAMPLES
        ],
    }


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
        'ticket_nav': _ticket_nav(lang),
        'kinoteatr_nav': _kinoteatr_nav(lang),
        'genres': _ordered_genres(),
        'current_language': lang,
        'has_subscription': user_has_subscription(request.user),
        'has_movie_access': user_can_watch_movies(request.user),
        'has_live_access': user_can_watch_live(request.user),
    }
