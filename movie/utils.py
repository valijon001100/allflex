import uuid
from datetime import timedelta

from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import CorporateMember, CorporateMovieShareLink, CorporateOrganization, UserSubscription

SESSION_REFERRAL_KEY = 'corporate_referral_code'
SESSION_MOVIE_SHARE_KEY = 'corporate_movie_share'


def get_corporate_membership(user):
    if not user.is_authenticated:
        return None
    return CorporateMember.objects.filter(
        user=user,
        organization__is_active=True,
        organization__end_date__gt=timezone.now(),
    ).select_related('organization', 'organization__plan').first()


def get_active_subscription(user):
    if not user.is_authenticated:
        return None
    return UserSubscription.objects.filter(
        user=user,
        is_active=True,
        end_date__gt=timezone.now(),
    ).select_related('plan').order_by('-end_date').first()


def _get_access_plan(user):
    corp = get_corporate_membership(user)
    if corp:
        return corp.organization.plan
    sub = get_active_subscription(user)
    return sub.plan if sub else None


def user_has_subscription(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return get_active_subscription(user) is not None or get_corporate_membership(user) is not None


def user_can_watch_movies(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    plan = _get_access_plan(user)
    return bool(plan and plan.access_movies)


def get_movie_share_access(request, movie):
    if not request or not movie:
        return None
    data = request.session.get(SESSION_MOVIE_SHARE_KEY)
    if not data or data.get('movie_id') != movie.pk:
        return None
    link = CorporateMovieShareLink.objects.filter(
        token=data.get('token'),
        movie=movie,
        is_active=True,
    ).select_related('member__organization', 'member__organization__plan').first()
    if link and link.is_valid:
        return link
    request.session.pop(SESSION_MOVIE_SHARE_KEY, None)
    return None


def user_can_watch_movie(user, movie, request=None):
    if user.is_authenticated and user.is_staff:
        return True
    if user.is_authenticated and user_can_watch_movies(user):
        return True
    if request and get_movie_share_access(request, movie):
        return True
    return False


def get_or_create_movie_share_link(member, movie):
    expires_at = member.organization.end_date
    link, created = CorporateMovieShareLink.objects.get_or_create(
        member=member,
        movie=movie,
        defaults={
            'token': uuid.uuid4().hex[:16],
            'expires_at': expires_at,
        },
    )
    if not created and link.expires_at < expires_at:
        link.expires_at = expires_at
        link.save(update_fields=['expires_at'])
    return link


def activate_movie_share_session(request, link):
    request.session[SESSION_MOVIE_SHARE_KEY] = {
        'token': link.token,
        'movie_id': link.movie_id,
    }
    CorporateMovieShareLink.objects.filter(pk=link.pk).update(
        views_count=F('views_count') + 1,
    )


def verify_movie_share_token(token, movie_id):
    if not token:
        return False
    link = CorporateMovieShareLink.objects.filter(
        token=token,
        movie_id=movie_id,
        is_active=True,
    ).select_related('member__organization').first()
    return bool(link and link.is_valid)


def user_can_watch_live(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    plan = _get_access_plan(user)
    return bool(plan and plan.access_live)


def grant_subscription(user, plan, payment_amount):
    now = timezone.now()
    active = get_active_subscription(user)

    if active:
        active.end_date = active.end_date + timedelta(days=plan.duration_days)
        active.payment_amount = payment_amount
        active.plan = plan
        active.save(update_fields=['end_date', 'payment_amount', 'plan'])
        return active

    return UserSubscription.objects.create(
        user=user,
        plan=plan,
        start_date=now,
        end_date=now + timedelta(days=plan.duration_days),
        payment_amount=payment_amount,
        is_active=True,
    )


def cancel_subscription(user):
    sub = get_active_subscription(user)
    if not sub:
        return False
    sub.is_active = False
    sub.save(update_fields=['is_active'])
    return True


def approve_corporate_request(request_obj, admin_user=None):
    """Tasdiqlangan korporativ so'rovdan tashkilot yaratadi."""
    from .models import CorporateSubscriptionRequest

    if request_obj.status != CorporateSubscriptionRequest.STATUS_PENDING:
        return None

    now = timezone.now()
    seats = min(request_obj.seats_requested, request_obj.plan.max_seats)
    org = CorporateOrganization.objects.create(
        company_name=request_obj.company_name,
        plan=request_obj.plan,
        contact_name=request_obj.contact_name,
        contact_email=request_obj.email,
        contact_phone=request_obj.phone,
        admin_user=request_obj.user,
        max_seats=seats,
        start_date=now,
        end_date=now + timedelta(days=request_obj.plan.duration_days),
        is_active=True,
    )

    if request_obj.user:
        CorporateMember.objects.get_or_create(
            organization=org,
            user=request_obj.user,
        )

    request_obj.status = CorporateSubscriptionRequest.STATUS_APPROVED
    request_obj.processed_at = now
    request_obj.save(update_fields=['status', 'processed_at'])
    return org


def store_pending_referral(request, code):
    request.session[SESSION_REFERRAL_KEY] = code


def get_referrer_member(code):
    if not code:
        return None
    return CorporateMember.objects.filter(
        referral_code=code,
    ).select_related('organization', 'organization__plan', 'user').first()


def join_corporate_via_referral(user, code):
    referrer = get_referrer_member(code)
    if not referrer:
        return False, _('Referal havola noto\'g\'ri yoki muddati tugagan.')

    org = referrer.organization
    if not org.is_valid:
        return False, _('Korporativ obuna muddati tugagan.')

    if org.seats_available <= 0:
        return False, _('Barcha korporativ o\'rinlar band.')

    if CorporateMember.objects.filter(user=user, organization=org).exists():
        return False, _('Siz allaqachon bu kompaniya a\'zosisiz.')

    if get_corporate_membership(user):
        return False, _('Siz boshqa korporativ obunadasiz.')

    CorporateMember.objects.create(
        organization=org,
        user=user,
        referred_by=referrer,
    )
    return True, _('Korporativ obunaga muvaffaqiyatli qo\'shildingiz!')


def try_apply_pending_referral(request):
    code = request.session.pop(SESSION_REFERRAL_KEY, None)
    if not code or not request.user.is_authenticated:
        return False
    ok, msg = join_corporate_via_referral(request.user, code)
    if ok:
        from django.contrib import messages
        messages.success(request, msg)
        return True
    from django.contrib import messages
    messages.warning(request, msg)
    return False
