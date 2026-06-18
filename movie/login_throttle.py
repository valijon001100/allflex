from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .stream_utils import client_ip

MAX_ATTEMPTS = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)
ATTEMPT_WINDOW = getattr(settings, 'LOGIN_ATTEMPT_WINDOW', 300)
LOCKOUT_SECONDS = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 300)


def _fail_key(ip):
    return f'login_fail:{ip}'


def _lock_key(ip):
    return f'login_lock:{ip}'


def login_lock_status(request):
    ip = client_ip(request)
    locked_until = cache.get(_lock_key(ip))
    if not locked_until:
        return False, 0
    remaining = int(locked_until - timezone.now().timestamp())
    if remaining <= 0:
        cache.delete(_lock_key(ip))
        return False, 0
    return True, remaining


def record_failed_login(request):
    ip = client_ip(request)
    fail_key = _fail_key(ip)
    count = cache.get(fail_key, 0) + 1
    cache.set(fail_key, count, ATTEMPT_WINDOW)
    if count >= MAX_ATTEMPTS:
        cache.set(
            _lock_key(ip),
            timezone.now().timestamp() + LOCKOUT_SECONDS,
            LOCKOUT_SECONDS,
        )
        cache.delete(fail_key)
        return True
    return False


def clear_login_attempts(request):
    ip = client_ip(request)
    cache.delete(_fail_key(ip))
    cache.delete(_lock_key(ip))
