from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import CorporateMovieShareLink
from .utils import (
    SESSION_REFERRAL_KEY,
    activate_movie_share_session,
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


def corporate_movie_share(request, token):
    link = CorporateMovieShareLink.objects.filter(
        token=token,
        is_active=True,
    ).select_related('movie', 'member__organization').first()
    if not link or not link.is_valid:
        return render(request, 'corporate/share_invalid.html', status=404)

    activate_movie_share_session(request, link)
    messages.info(
        request,
        _('«%(title)s» — 9 daqiqa bepul ko\'rish, keyin ro\'yxatdan o\'ting (faqat shu kino ochiq).')
        % {'title': link.movie.get_translated_title()},
    )
    return redirect('movie:detail', slug=link.movie.slug)


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
