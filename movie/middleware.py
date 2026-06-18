from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


STAFF_ALLOWED_PREFIXES = (
    '/panel/',
    '/login/',
    '/registration/',
    '/logout/',
    '/admin/',
    '/static/',
    '/media/',
    '/live/',
    '/i18n/',
    '/subscription/',
    '/subscribe/',
    '/my-subscription/',
    '/payment/',
    '/stream/',
)


class StaffRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.user.is_staff
            and not any(request.path.startswith(prefix) for prefix in STAFF_ALLOWED_PREFIXES)
        ):
            return redirect('movie:admin_dashboard')
        return self.get_response(request)


class ProtectedMediaMiddleware:
    """Block all direct access to uploaded movie video files."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefix = settings.MEDIA_URL + 'movies/videos/'
        self.trailer_prefix = settings.MEDIA_URL + 'movies/trailers/'

    def __call__(self, request):
        if request.path.startswith(self.prefix) or request.path.startswith(self.trailer_prefix):
            return HttpResponseForbidden(
                'Videoni yuklab olish yoki to\'g\'ridan-to\'g\'ri ochish taqiqlangan.',
            )
        return self.get_response(request)
