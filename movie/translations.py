CATEGORY_NAMES = {
    'filmy': {'uz': 'Filmlar', 'ru': 'Фильмы', 'en': 'Movies'},
    'serialy': {'uz': 'Seriallar', 'ru': 'Сериалы', 'en': 'TV Series'},
    'teleperedachi': {'uz': 'Teleko\'rsatuvlar', 'ru': 'Телепередачи', 'en': 'TV Shows'},
    'multfilmy': {'uz': 'Multfilmlar', 'ru': 'Мультфильмы', 'en': 'Cartoons'},
    'skoro-na-sajte': {'uz': 'Tez kunda', 'ru': 'Скоро на сайте', 'en': 'Coming Soon'},
    'podborki': {'uz': 'To\'plamlar', 'ru': 'Подборки', 'en': 'Collections'},
}


def translate_category(category, lang):
    if category.name_uz or category.name_en:
        return category.get_translated_name(lang)
    names = CATEGORY_NAMES.get(category.slug, {})
    return names.get(lang, category.name)
