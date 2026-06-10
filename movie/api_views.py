import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import APIAccessLog, APIPartner, Movie, PiracyAlert


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _log_api(request, endpoint, partner=None, authorized=False):
    APIAccessLog.objects.create(
        partner=partner,
        endpoint=endpoint,
        ip_address=_client_ip(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:300],
        is_authorized=authorized,
    )


def _get_partner(request):
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key', '')
    if not api_key:
        return None
    return APIPartner.objects.filter(api_key=api_key, is_active=True).first()


def _movie_api_dict(movie, request):
    return {
        'uid': movie.movie_uid,
        'title': movie.title,
        'slug': movie.slug,
        'digital_passport': movie.digital_passport_code,
        'category': movie.category.name,
        'year': movie.year,
        'duration': movie.duration,
        'rating': movie.rating,
        'poster': request.build_absolute_uri(movie.poster.url) if movie.poster else '',
        'embed_url': request.build_absolute_uri(f'/movie/{movie.slug}/'),
        'is_premium': movie.is_premium,
        'legal_notice': 'Faqat ruxsat etilgan API orqali tarqatish. Reklama daromadidan ulush beriladi.',
    }


def content_api_info(request):
    return render(request, 'content_api/info.html', {
        'partners_count': APIPartner.objects.filter(is_active=True).count(),
    })


@require_GET
def api_movies_list(request):
    partner = _get_partner(request)
    if not partner:
        _log_api(request, '/api/v1/movies/', authorized=False)
        PiracyAlert.objects.create(
            detected_domain=request.META.get('HTTP_REFERER', '')[:200],
            description='API kalitsiz yoki noto\'g\'ri kalit bilan film ro\'yxati so\'rovi',
            ip_address=_client_ip(request),
        )
        return JsonResponse({'error': 'Invalid or missing API key'}, status=401)

    partner.total_requests += 1
    partner.save(update_fields=['total_requests'])
    _log_api(request, '/api/v1/movies/', partner=partner, authorized=True)

    movies = Movie.objects.select_related('category').order_by('-created_at')[:100]
    return JsonResponse({
        'partner': partner.name,
        'revenue_share_percent': partner.revenue_share_percent,
        'count': movies.count(),
        'movies': [_movie_api_dict(m, request) for m in movies],
    })


@require_GET
def api_movie_detail(request, movie_uid):
    partner = _get_partner(request)
    if not partner:
        _log_api(request, f'/api/v1/movies/{movie_uid}/', authorized=False)
        PiracyAlert.objects.create(
            movie=Movie.objects.filter(movie_uid=movie_uid).first(),
            description=f'API kalitsiz film so\'rovi: {movie_uid}',
            ip_address=_client_ip(request),
        )
        return JsonResponse({'error': 'Invalid or missing API key'}, status=401)

    movie = get_object_or_404(Movie, movie_uid=movie_uid)
    partner.total_requests += 1
    partner.save(update_fields=['total_requests'])
    _log_api(request, f'/api/v1/movies/{movie_uid}/', partner=partner, authorized=True)
    return JsonResponse(_movie_api_dict(movie, request))


@csrf_exempt
@require_http_methods(['POST'])
def api_report_piracy(request):
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        body = {}

    movie_uid = body.get('movie_uid', '')
    movie = Movie.objects.filter(movie_uid=movie_uid).first() if movie_uid else None
    domain = body.get('domain', '')[:200]
    url = body.get('url', '')[:500]
    desc = body.get('description', _('Noqonuniy joylashtirish aniqlandi'))

    alert = PiracyAlert.objects.create(
        movie=movie,
        detected_url=url,
        detected_domain=domain,
        description=desc,
        ip_address=_client_ip(request),
        notified_rights_holder=True,
    )
    return JsonResponse({'status': 'reported', 'alert_id': alert.pk})
