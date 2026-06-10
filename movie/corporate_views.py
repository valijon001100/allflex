from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .utils import (
    SESSION_REFERRAL_KEY,
    get_corporate_membership,
    get_referrer_member,
    join_corporate_via_referral,
    store_pending_referral,
)


def corporate_join(request, code):
    referrer = get_referrer_member(code)
    if not referrer:
        return render(request, 'corporate/join_invalid.html', status=404)

    org = referrer.organization
    store_pending_referral(request, code)

    if request.method == 'POST' and request.user.is_authenticated:
        ok, msg = join_corporate_via_referral(request.user, code)
        if ok:
            messages.success(request, msg)
            request.session.pop(SESSION_REFERRAL_KEY, None)
            return redirect('movie:my_subscription')
        messages.error(request, msg)

    already_member = False
    if request.user.is_authenticated:
        already_member = get_corporate_membership(request.user) is not None

    referral_url = request.build_absolute_uri(referrer.get_referral_path())
    return render(request, 'corporate/join.html', {
        'referrer': referrer,
        'org': org,
        'referral_url': referral_url,
        'already_member': already_member,
        'seats_available': org.seats_available,
        'org_valid': org.is_valid,
    })


@login_required
@require_POST
def corporate_join_confirm(request, code):
    ok, msg = join_corporate_via_referral(request.user, code)
    if ok:
        messages.success(request, msg)
        request.session.pop(SESSION_REFERRAL_KEY, None)
        return redirect('movie:my_subscription')
    messages.error(request, msg)
    return redirect('movie:corporate_join', code=code)
