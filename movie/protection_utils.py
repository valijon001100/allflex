import hashlib
import json
import secrets
import string

from django.utils import timezone


def _rand_alnum(length, upper=True):
    chars = string.ascii_uppercase + string.digits if upper else string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_movie_uid():
    return f'AFLX-{_rand_alnum(8)}'


def generate_watermark_token():
    return f'WM-{_rand_alnum(12)}'


def generate_digital_passport(movie_uid, title, watermark_token):
    raw = f'{movie_uid}|{title}|{watermark_token}|{timezone.now().isoformat()}'
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    payload = {
        'uid': movie_uid,
        'title': title,
        'watermark': watermark_token,
        'hash': digest,
        'issued': timezone.now().strftime('%Y-%m-%d'),
        'issuer': 'AL-FLIX Content Protection',
    }
    return json.dumps(payload, ensure_ascii=False), f'DP-{movie_uid}-{digest}'


def generate_subscriber_code():
    return _rand_alnum(10)


def generate_api_key():
    return f'alfx_{secrets.token_urlsafe(32)}'
