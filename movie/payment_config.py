from django.conf import settings

from .models import PaymentSettings


def _db():
    return PaymentSettings.load()


def get_click_config():
    ps = _db()
    return {
        'merchant_id': (ps.click_merchant_id or settings.CLICK_MERCHANT_ID or '').strip(),
        'service_id': (ps.click_service_id or settings.CLICK_SERVICE_ID or '').strip(),
        'secret_key': (ps.click_secret_key or settings.CLICK_SECRET_KEY or '').strip(),
    }


def get_payme_config():
    ps = _db()
    return {
        'merchant_id': (ps.payme_merchant_id or settings.PAYME_MERCHANT_ID or '').strip(),
        'secret_key': (ps.payme_secret_key or settings.PAYME_SECRET_KEY or '').strip(),
    }


def click_configured():
    cfg = get_click_config()
    return all(cfg.values())


def payme_configured():
    cfg = get_payme_config()
    return all(cfg.values())


def payment_configured():
    return click_configured() or payme_configured()


def test_mode_available():
    if not settings.DEBUG:
        return False
    return _db().test_mode_enabled
