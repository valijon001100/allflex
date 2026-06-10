from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import PaymentOrder, PurchasedTicket, TicketCategory, TicketEvent
from .payment_config import click_configured, payme_configured, test_mode_available
from .payment_views import _payment_context
from .payments import _mark_order_paid, get_click_payment_url, get_payme_checkout_url


def _ticket_categories(lang):
    return [
        {'obj': cat, 'name': cat.get_translated_name(lang)}
        for cat in TicketCategory.objects.filter(is_active=True)
    ]


def ticket_home(request):
    lang = getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru'
    base_qs = TicketEvent.objects.filter(
        is_active=True, event_date__gte=timezone.now(),
    ).select_related('category')
    premieres = base_qs.filter(is_premiere=True).order_by('event_date')[:16]
    events = base_qs.order_by('event_date')[:12]
    return render(request, 'tickets/home.html', {
        'categories': _ticket_categories(lang),
        'premieres': premieres,
        'events': events,
    })


def ticket_category(request, slug):
    lang = getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru'
    category = get_object_or_404(TicketCategory, slug=slug, is_active=True)
    base_qs = category.events.filter(
        is_active=True, event_date__gte=timezone.now(),
    )
    premieres = base_qs.filter(is_premiere=True).order_by('event_date')
    events = base_qs.order_by('event_date')
    return render(request, 'tickets/category.html', {
        'category': category,
        'category_name': category.get_translated_name(lang),
        'categories': _ticket_categories(lang),
        'premieres': premieres,
        'events': events,
    })


def ticket_detail(request, slug):
    event = get_object_or_404(
        TicketEvent.objects.select_related('category'),
        slug=slug, is_active=True,
    )
    lang = getattr(request, 'LANGUAGE_CODE', 'ru') or 'ru'
    ctx = _payment_context()
    ctx.update({
        'event': event,
        'category_name': event.category.get_translated_name(lang),
    })
    return render(request, 'tickets/detail.html', ctx)


@login_required
@require_POST
def ticket_checkout(request):
    event_id = request.POST.get('event_id')
    provider = request.POST.get('provider')
    try:
        quantity = max(1, min(10, int(request.POST.get('quantity', 1))))
    except (TypeError, ValueError):
        quantity = 1

    event = get_object_or_404(TicketEvent, pk=event_id, is_active=True)

    if event.is_sold_out or event.tickets_left < quantity:
        messages.error(request, _('Biletlar tugagan.'))
        return redirect(event.get_absolute_url())

    if provider == PaymentOrder.PROVIDER_CLICK:
        if not click_configured():
            return render(request, 'subscription/payment_fail.html', {
                'message': _('Click to\'lov tizimi sozlanmagan.'),
            })
    elif provider == PaymentOrder.PROVIDER_PAYME:
        if not payme_configured():
            return render(request, 'subscription/payment_fail.html', {
                'message': _('Payme to\'lov tizimi sozlanmagan.'),
            })
    else:
        return HttpResponseBadRequest('Invalid provider')

    amount = event.price * quantity
    order = PaymentOrder.objects.create(
        user=request.user,
        order_type=PaymentOrder.ORDER_TICKET,
        ticket_event=event,
        ticket_quantity=quantity,
        provider=provider,
        amount=amount,
    )

    if provider == PaymentOrder.PROVIDER_CLICK:
        return redirect(get_click_payment_url(
            order, request, return_view='movie:ticket_payment_success',
        ))
    return redirect(get_payme_checkout_url(
        order, request, return_view='movie:ticket_payment_success',
    ))


@login_required
@require_POST
def test_ticket_purchase(request):
    if not test_mode_available():
        return HttpResponseBadRequest('Test mode disabled')

    event = get_object_or_404(TicketEvent, pk=request.POST.get('event_id'), is_active=True)
    try:
        quantity = max(1, min(10, int(request.POST.get('quantity', 1))))
    except (TypeError, ValueError):
        quantity = 1

    if event.tickets_left < quantity:
        messages.error(request, _('Biletlar tugagan.'))
        return redirect(event.get_absolute_url())

    order = PaymentOrder.objects.create(
        user=request.user,
        order_type=PaymentOrder.ORDER_TICKET,
        ticket_event=event,
        ticket_quantity=quantity,
        provider=PaymentOrder.PROVIDER_TEST,
        amount=event.price * quantity,
    )
    _mark_order_paid(order, 'test')
    messages.success(request, _('Bilet muvaffaqiyatli sotib olindi!'))
    return redirect('movie:ticket_payment_success')


@login_required
def my_tickets(request):
    tickets = PurchasedTicket.objects.filter(
        user=request.user,
    ).select_related('event', 'event__category').order_by('-created_at')
    return render(request, 'tickets/my_tickets.html', {'tickets': tickets})


@login_required
def ticket_payment_success(request):
    tickets = PurchasedTicket.objects.filter(
        user=request.user,
    ).select_related('event').order_by('-created_at')[:20]
    return render(request, 'tickets/payment_success.html', {'tickets': tickets})
