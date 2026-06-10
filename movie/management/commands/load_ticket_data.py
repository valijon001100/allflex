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
        ('kino', 'Avatar 3 — prem\'yera', 'avatar-3-premyera', 'Humo Arena', 85000, 200),
        ('kino', 'O\'zbek kino kechasi', 'uzbek-kino-kechasi', 'Milliy kino markazi', 45000, 150),
        ('teatr', 'Alisher Navoiy — spektakl', 'navoiy-spektakl', 'O\'zbek milliy teatri', 120000, 80),
        ('teatr', 'Vijdon azobi', 'vijdon-azobi', 'Yoshlar teatri', 75000, 100),
        ('sirk', 'Sirk shousi — bahor', 'sirk-bahor', 'Toshkent sirk', 60000, 300),
        ('sirk', 'Delfinlar shousi', 'delfinlar-shousi', 'Aqua Park', 90000, 120),
    ]
    for i, (slug, title, ev_slug, venue, price, qty) in enumerate(samples):
        TicketEvent.objects.create(
            category=cat_map[slug],
            title=title,
            slug=ev_slug,
            description=f'{title} — onlayn bilet orqali sotib oling.',
            venue=venue,
            city='Toshkent',
            event_date=now + timedelta(days=7 + i * 3),
            price=price,
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
