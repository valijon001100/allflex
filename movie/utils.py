from datetime import timedelta

from django.utils import timezone

from .models import CorporateMember, CorporateOrganization, UserSubscription


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
        CorporateMember.objects.get_or_create(organization=org, user=request_obj.user)

    request_obj.status = CorporateSubscriptionRequest.STATUS_APPROVED
    request_obj.processed_at = now
    request_obj.save(update_fields=['status', 'processed_at'])
    return org
