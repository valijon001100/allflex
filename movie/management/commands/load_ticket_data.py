from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from movie.models import TicketCategory, TicketEvent

CATEGORY_DATA = [
    {'name': 'Кино', 'name_uz': 'Kinoteatr', 'name_en': 'Cinema', 'slug': 'kino', 'icon': '🎬', 'order': 1},
    {'name': 'Театр', 'name_uz': 'Teatr', 'name_en': 'Theater', 'slug': 'teatr', 'icon': '🎭', 'order': 2},
    {'name': 'Цирк', 'name_uz': 'Sirk', 'name_en': 'Circus', 'slug': 'sirk', 'icon': '🎪', 'order': 3},
]

SAMPLE_EVENTS = [
    ('kino', 'Avatar 3', 'avatar-3-premyera', 'PREMYERA', 'Humo Arena', 'Toshkent, Humo Arena', 85000, 200, '12+', 'O\'zbekcha'),
    ('kino', 'O\'zbek kino kechasi', 'uzbek-kino-kechasi', 'JONLI TOMOSHA', 'Milliy kino markazi', 'Toshkent, Navoiy ko\'chasi 2', 45000, 150, '6+', 'O\'zbekcha'),
    ('teatr', 'Alisher Navoiy', 'navoiy-spektakl', 'MILLIY TEATR', 'O\'zbek milliy teatri', 'Toshkent, Atamurat ota ko\'chasi 1', 120000, 80, '6+', 'O\'zbekcha'),
    ('teatr', 'Vijdon azobi', 'vijdon-azobi', 'DRAMA', 'Yoshlar teatri', 'Toshkent, Amir Temur shoh ko\'chasi', 75000, 100, '16+', 'O\'zbekcha'),
    ('sirk', 'Sirk shousi — bahor', 'sirk-bahor', 'SIRK SHOUSI', 'Toshkent sirk', 'Toshkent, Bobur ko\'chasi 14', 60000, 300, '3+', 'Ko\'p tilli'),
    ('sirk', 'Delfinlar shousi', 'delfinlar-shousi', 'SHOU', 'Aqua Park', 'Toshkent, Yunusobod tumani', 90000, 120, '0+', 'Ko\'p tilli'),
]


def ensure_categories():
    created = 0
    for data in CATEGORY_DATA:
        cat, was_created = TicketCategory.objects.get_or_create(
            slug=data['slug'],
            defaults=data,
        )
        if was_created:
            created += 1
        elif cat.name_uz != data['name_uz'] or cat.name != data['name']:
            cat.name_uz = data['name_uz']
            cat.name = data['name']
            cat.name_en = data['name_en']
            cat.icon = data['icon']
            cat.save(update_fields=['name_uz', 'name', 'name_en', 'icon'])
    return created


def ensure_sample_events():
    if TicketEvent.objects.exists():
        return 0

    cat_map = {c.slug: c for c in TicketCategory.objects.all()}
    if len(cat_map) < len(CATEGORY_DATA):
        ensure_categories()
        cat_map = {c.slug: c for c in TicketCategory.objects.all()}

    now = timezone.now()
    created = 0
    for i, row in enumerate(SAMPLE_EVENTS):
        slug, title, ev_slug, subtitle, venue, address, price, qty, age, lang = row
        category = cat_map.get(slug)
        if not category:
            continue
        TicketEvent.objects.create(
            category=category,
            title=title,
            slug=ev_slug,
            subtitle=subtitle,
            description=(
                f'{title} — {subtitle.lower()} bo\'yicha noyob tadbir. '
                f'Joy: {venue}. Biletlarni onlayn xarid qiling va zavq bilan tomosha qiling.'
            ),
            venue=venue,
            venue_address=address,
            city='Toshkent',
            event_date=now + timedelta(days=7 + i * 3),
            price=price,
            age_limit=age,
            language=lang,
            is_premiere=True,
            quantity_total=qty,
            is_active=True,
        )
        created += 1
    return created


def seed_tickets():
    cats = ensure_categories()
    events = ensure_sample_events()
    return cats, events


class Command(BaseCommand):
    help = 'Bilet bo\'limlari va namuna tadbirlarni yuklaydi'

    def handle(self, *args, **options):
        cats, events = seed_tickets()
        if cats or events:
            self.stdout.write(self.style.SUCCESS(
                f'Yuklandi: {cats} yangi bo\'lim, {events} yangi tadbir '
                f'(jami: {TicketCategory.objects.count()} bo\'lim, '
                f'{TicketEvent.objects.count()} tadbir)',
            ))
        else:
            self.stdout.write('Bilet ma\'lumotlari allaqachon mavjud.')
