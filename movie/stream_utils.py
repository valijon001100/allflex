import re
import shutil
import subprocess
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

STREAM_SALT = 'alflix-stream-v1'
STREAM_MAX_AGE = 60 * 60 * 4

DOWNLOAD_USER_AGENTS = (
    'wget', 'curl/', 'python-requests', 'aria2', 'idm', 'internet download manager',
    'freedownloadmanager', 'jdownloader', 'ffmpeg', 'libwww', 'go-http-client',
    'httpx', 'scrapy', 'okhttp', 'postman', 'insomnia',
)


def sign_stream_path(path, movie_id, quality, user_id):
    payload = {'m': int(movie_id), 'q': str(quality), 'u': int(user_id)}
    sig = signing.dumps(payload, salt=STREAM_SALT)
    return f'{path}?sig={sig}'


def verify_stream_request(request, movie_id, quality, user_id):
    sig = request.GET.get('sig', '')
    if not sig:
        return False
    try:
        data = signing.loads(sig, salt=STREAM_SALT, max_age=STREAM_MAX_AGE)
    except signing.BadSignature:
        return False
    return (
        data.get('m') == int(movie_id)
        and data.get('q') == str(quality)
        and data.get('u') == int(user_id)
    )


def ffmpeg_available():
    return shutil.which('ffmpeg') is not None


def server_watermark_enabled():
    mode = getattr(settings, 'WATERMARK_BURN_STREAM', 'auto').lower()
    if mode in ('0', 'false', 'no', 'off'):
        return False
    if mode in ('1', 'true', 'yes', 'on'):
        return ffmpeg_available()
    return ffmpeg_available()


def _escape_ffmpeg_text(text):
    safe = re.sub(r'[^A-Za-z0-9]', '', text or '')
    return safe.replace('\\', '\\\\').replace("'", "\\'").replace(':', '\\:')


def iter_watermarked_video(path, subscriber_code):
    if not ffmpeg_available() or not subscriber_code:
        return None
    code = _escape_ffmpeg_text(subscriber_code)
    if not code:
        return None
    vf = (
        f"drawtext=text='{code}':fontsize=14:fontcolor=white@0.92:"
        f"shadowcolor=black@0.85:shadowx=1:shadowy=1:"
        f"x='12+mod(t*28\\,w-tw-24)':y='12+mod(t*20\\,h-th-48)'"
    )
    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error',
        '-i', path,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
        '-c:a', 'copy',
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
        '-f', 'mp4', 'pipe:1',
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def generator():
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            if proc.poll() is None:
                proc.kill()

    return generator


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_watch_history(request, user, movie, profile=None):
    from .models import WatchHistory

    if not user.is_authenticated or not movie:
        return
    since = timezone.now() - timedelta(minutes=10)
    if WatchHistory.objects.filter(
        user=user, movie=movie, watched_at__gte=since,
    ).exists():
        return
    code = ''
    if profile and profile.subscriber_code:
        code = profile.subscriber_code
    WatchHistory.objects.create(
        user=user,
        movie=movie,
        subscriber_code=code,
        ip_address=client_ip(request),
    )
