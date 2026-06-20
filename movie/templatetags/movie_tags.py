from django import template

register = template.Library()


@register.filter
def movie_title(movie):
    return movie.get_translated_title()


@register.filter
def genre_name(genre, lang=None):
    if lang is None:
        from django.utils.translation import get_language
        lang = get_language() or 'uz'
    return genre.get_translated_name(lang)
