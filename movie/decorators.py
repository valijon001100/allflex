from functools import wraps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def admin_required(view_func):
    @wraps(view_func)
    @login_required(login_url=settings.LOGIN_URL)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect('movie:home')
        return view_func(request, *args, **kwargs)
    return wrapper
