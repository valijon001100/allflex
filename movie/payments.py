import base64
import hashlib
import json
import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import PaymentOrder
from .payment_config import click_configured, get_click_config, get_payme_config, payme_configured
from .utils import grant_subscription

logger = logging.getLogger(__name__)

_click_configured = click_configured
_payme_configured = payme_configured


def click_sign(*parts):
    raw = ''.join(str(p) for p in parts)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def verify_click_sign(params, action):
    secret = get_click_config()['secret_key']
    base = [
        params.get('click_trans_id', ''),
        params.get('service_id', ''),
        secret,
        params.get('merchant_trans_id', ''),
    ]
    if action == 1:
        base.append(params.get('merchant_prepare_id', ''))
    base.extend([
        params.get('amount', ''),
        action,
        params.get('sign_time', ''),
    ])
    return params.get('sign_string', '') == click_sign(*base)


def get_click_payment_url(order, request):
    cfg = get_click_config()
    return_url = request.build_absolute_uri(reverse('movie:payment_success'))
    return (
        'https://my.click.uz/services/pay'
        f'?service_id={cfg["service_id"]}'
        f'&merchant_id={cfg["merchant_id"]}'
        f'&amount={order.amount}'
        f'&transaction_param={order.order_id}'
        f'&return_url={return_url}'
    )


def get_payme_checkout_url(order, request):
    cfg = get_payme_config()
    return_url = request.build_absolute_uri(reverse('movie:payment_success'))
    payload = {
        'm': cfg['merchant_id'],
        'ac': {'order_id': str(order.order_id)},
        'a': order.amount_tiyin,
        'c': return_url,
    }
    encoded = base64.b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode()
    return f'https://checkout.paycom.uz/{encoded}'


def handle_click_prepare(params):
    if not verify_click_sign(params, 0):
        return {'error': -1, 'error_note': 'Invalid sign'}

    try:
        order = PaymentOrder.objects.get(
            order_id=params.get('merchant_trans_id'),
            provider=PaymentOrder.PROVIDER_CLICK,
        )
    except PaymentOrder.DoesNotExist:
        return {'error': -5, 'error_note': 'Order not found'}

    if order.status == PaymentOrder.STATUS_PAID:
        return {'error': -4, 'error_note': 'Already paid'}

    amount = float(params.get('amount', 0))
    if amount != float(order.amount):
        return {'error': -2, 'error_note': 'Invalid amount'}

    order.prepare_id = str(params.get('click_trans_id', ''))
    order.save(update_fields=['prepare_id'])
    return {
        'error': 0,
        'error_note': 'Success',
        'merchant_prepare_id': order.pk,
    }


def handle_click_complete(params):
    if not verify_click_sign(params, 1):
        return {'error': -1, 'error_note': 'Invalid sign'}

    try:
        order = PaymentOrder.objects.get(
            order_id=params.get('merchant_trans_id'),
            provider=PaymentOrder.PROVIDER_CLICK,
        )
    except PaymentOrder.DoesNotExist:
        return {'error': -5, 'error_note': 'Order not found'}

    if order.status == PaymentOrder.STATUS_PAID:
        return {'error': -4, 'error_note': 'Already paid'}

    amount = float(params.get('amount', 0))
    if amount != float(order.amount):
        return {'error': -2, 'error_note': 'Invalid amount'}

    _mark_order_paid(order, params.get('click_trans_id', ''))
    return {
        'error': 0,
        'error_note': 'Success',
        'merchant_confirm_id': order.pk,
    }


def _mark_order_paid(order, external_id=''):
    if order.status == PaymentOrder.STATUS_PAID:
        return
    order.status = PaymentOrder.STATUS_PAID
    order.external_id = str(external_id)
    order.paid_at = timezone.now()
    order.save(update_fields=['status', 'external_id', 'paid_at'])
    grant_subscription(order.user, order.plan, order.amount)


def _payme_auth_ok(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth.startswith('Basic '):
        return False
    try:
        decoded = base64.b64decode(auth[6:]).decode('utf-8')
    except Exception:
        return False
    return decoded == f'Paycom:{get_payme_config()["secret_key"]}'


def handle_payme_request(request):
    if not _payme_configured():
        return {'error': {'code': -32400, 'message': 'Payme not configured'}}

    if not _payme_auth_ok(request):
        return {'error': {'code': -32504, 'message': 'Unauthorized'}}

    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return {'error': {'code': -32700, 'message': 'Parse error'}}

    method = body.get('method')
    params = body.get('params', {})
    req_id = body.get('id')

    handlers = {
        'CheckPerformTransaction': _payme_check_perform,
        'CreateTransaction': _payme_create_transaction,
        'PerformTransaction': _payme_perform_transaction,
        'CancelTransaction': _payme_cancel_transaction,
        'CheckTransaction': _payme_check_transaction,
    }
    handler = handlers.get(method)
    if not handler:
        return {'error': {'code': -32601, 'message': 'Method not found'}, 'id': req_id}

    try:
        result = handler(params)
        return {'result': result, 'id': req_id}
    except PaymeError as exc:
        return {'error': {'code': exc.code, 'message': exc.message}, 'id': req_id}


class PaymeError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _get_payme_order(params):
    account = params.get('account') or {}
    order_id = account.get('order_id')
    if not order_id:
        raise PaymeError(-31050, 'Order not found')
    try:
        return PaymentOrder.objects.get(
            order_id=order_id,
            provider=PaymentOrder.PROVIDER_PAYME,
        )
    except PaymentOrder.DoesNotExist:
        raise PaymeError(-31050, 'Order not found')


def _payme_check_perform(params):
    order = _get_payme_order(params)
    amount = params.get('amount')
    if amount != order.amount_tiyin:
        raise PaymeError(-31001, 'Invalid amount')
    if order.status == PaymentOrder.STATUS_PAID:
        raise PaymeError(-31050, 'Already paid')
    return {'allow': True}


def _payme_create_transaction(params):
    order = _get_payme_order(params)
    amount = params.get('amount')
    if amount != order.amount_tiyin:
        raise PaymeError(-31001, 'Invalid amount')
    if order.status == PaymentOrder.STATUS_PAID:
        raise PaymeError(-31050, 'Already paid')

    tx_id = str(params.get('id', ''))
    if order.external_id and order.external_id != tx_id:
        raise PaymeError(-31050, 'Transaction exists')

    if not order.external_id:
        order.external_id = tx_id
        order.save(update_fields=['external_id'])

    create_time = int(order.created_at.timestamp() * 1000)
    return {
        'create_time': create_time,
        'transaction': order.external_id,
        'state': 1,
    }


def _get_payme_order_by_tx(params):
    tx_id = str(params.get('id', ''))
    try:
        return PaymentOrder.objects.get(
            external_id=tx_id,
            provider=PaymentOrder.PROVIDER_PAYME,
        )
    except PaymentOrder.DoesNotExist:
        raise PaymeError(-31003, 'Transaction not found')


def _payme_perform_transaction(params):
    order = _get_payme_order_by_tx(params)
    if order.status != PaymentOrder.STATUS_PAID:
        _mark_order_paid(order, order.external_id)

    perform_time = int(timezone.now().timestamp() * 1000)
    return {
        'transaction': order.external_id,
        'perform_time': perform_time,
        'state': 2,
    }


def _payme_cancel_transaction(params):
    order = _get_payme_order_by_tx(params)
    order.status = PaymentOrder.STATUS_CANCELLED
    order.save(update_fields=['status'])

    cancel_time = int(timezone.now().timestamp() * 1000)
    return {
        'transaction': order.external_id,
        'cancel_time': cancel_time,
        'state': -1,
    }


def _payme_check_transaction(params):
    order = _get_payme_order_by_tx(params)
    state = 2 if order.status == PaymentOrder.STATUS_PAID else 1
    result = {
        'transaction': order.external_id,
        'state': state,
        'create_time': int(order.created_at.timestamp() * 1000),
    }
    if order.status == PaymentOrder.STATUS_PAID and order.paid_at:
        result['perform_time'] = int(order.paid_at.timestamp() * 1000)
    return result
