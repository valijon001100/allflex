from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from movie.models import TicketCategory, TicketEvent


def seed_tickets():
    if TicketCategory.objects.exists():
        return False

    categories = [
        {'name': 'Kino', 'name_uz': 'Kino', 'name_en': 'Cinema', 'slug': 'kino', 'icon': '🎬', 'order': 1},
        {'name': 'Театр', 'name_uz': 'Teatr', 'name_en': 'Theater', 'slug': 'teatr', 'icon': '🎭', 'order': 2},
        {'name': 'Цирк', 'name_uz': 'Sirk', 'name_en': 'Circus', 'slug': 'sirk', 'icon': '🎪', 'order': 3},
    ]
    cat_map = {}
    for data in categories:
        cat_map[data['slug']] = TicketCategory.objects.create(**data)

    now = timezone.now()
    samples = [
        ('kino', 'Avatar 3', 'avatar-3-premyera', 'PREMYERA', 'Humo Arena', 'Toshkent, Humo Arena', 85000, 200, '12+', 'O\'zbekcha'),
        ('kino', 'O\'zbek kino kechasi', 'uzbek-kino-kechasi', 'JONLI TOMOSHA', 'Milliy kino markazi', 'Toshkent, Navoiy ko\'chasi 2', 45000, 150, '6+', 'O\'zbekcha'),
        ('teatr', 'Alisher Navoiy', 'navoiy-spektakl', 'MILLIY TEATR', 'O\'zbek milliy teatri', 'Toshkent, Atamurat ota ko\'chasi 1', 120000, 80, '6+', 'O\'zbekcha'),
        ('teatr', 'Vijdon azobi', 'vijdon-azobi', 'DRAMA', 'Yoshlar teatri', 'Toshkent, Amir Temur shoh ko\'chasi', 75000, 100, '16+', 'O\'zbekcha'),
        ('sirk', 'Sirk shousi — bahor', 'sirk-bahor', 'SIRK SHOUSI', 'Toshkent sirk', 'Toshkent, Bobur ko\'chasi 14', 60000, 300, '3+', 'Ko\'p tilli'),
        ('sirk', 'Delfinlar shousi', 'delfinlar-shousi', 'SHOU', 'Aqua Park', 'Toshkent, Yunusobod tumani', 90000, 120, '0+', 'Ko\'p tilli'),
    ]
    for i, row in enumerate(samples):
        slug, title, ev_slug, subtitle, venue, address, price, qty, age, lang = row
        TicketEvent.objects.create(
            category=cat_map[slug],
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
    return True


class Command(BaseCommand):
    help = 'Bilet bo\'limlari va namuna tadbirlarni yuklaydi'

    def handle(self, *args, **options):
        if seed_tickets():
            self.stdout.write(self.style.SUCCESS(
                f'Yuklandi: {TicketCategory.objects.count()} bo\'lim, '
                f'{TicketEvent.objects.count()} tadbir',
            ))
        else:
            self.stdout.write('Bilet ma\'lumotlari allaqachon mavjud.')
