from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .utils import user_can_watch_movies


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
    """Block direct access to uploaded movie videos without subscription."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefix = settings.MEDIA_URL + 'movies/videos/'

    def __call__(self, request):
        if request.path.startswith(self.prefix):
            if not user_can_watch_movies(request.user):
                return HttpResponseForbidden()
        return self.get_response(request)
