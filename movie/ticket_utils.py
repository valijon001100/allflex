import secrets

from django.db import transaction
from django.db.models import F

from .models import PaymentOrder, PurchasedTicket, TicketEvent


def _generate_ticket_code():
    return secrets.token_hex(8).upper()


def fulfill_ticket_order(order):
    if order.order_type != PaymentOrder.ORDER_TICKET or not order.ticket_event_id:
        return
    if order.purchased_tickets.exists():
        return

    qty = order.ticket_quantity
    with transaction.atomic():
        event = TicketEvent.objects.select_for_update().get(pk=order.ticket_event_id)
        if event.tickets_left < qty:
            order.status = PaymentOrder.STATUS_ERROR
            order.save(update_fields=['status'])
            return

        TicketEvent.objects.filter(pk=event.pk).update(
            quantity_sold=F('quantity_sold') + qty,
        )

        for _ in range(qty):
            code = _generate_ticket_code()
            while PurchasedTicket.objects.filter(ticket_code=code).exists():
                code = _generate_ticket_code()
            PurchasedTicket.objects.create(
                order=order,
                user=order.user,
                event=event,
                ticket_code=code,
            )
