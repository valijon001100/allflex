from django import template

register = template.Library()


@register.filter
def movie_title(movie):
    return movie.get_translated_title()
