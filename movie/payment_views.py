import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.utils.translation import gettext as _

from .models import CorporateSubscriptionRequest, PaymentOrder, SubscriptionPlan
from django.contrib import messages

from .forms import CorporateRequestForm
from .payment_config import click_configured, payme_configured, test_mode_available
from .payments import (
    get_click_payment_url,
    get_payme_checkout_url,
    handle_click_complete,
    handle_click_prepare,
    handle_payme_request,
    _mark_order_paid,
)
from .utils import (
    cancel_subscription,
    get_active_subscription,
    get_corporate_membership,
    user_has_subscription,
)


def _payment_context():
    return {
        'click_ready': click_configured(),
        'payme_ready': payme_configured(),
        'test_mode': test_mode_available(),
    }


@login_required
def my_subscription(request):
    sub = get_active_subscription(request.user)
    corp = get_corporate_membership(request.user)
    return render(request, 'subscription/my_subscription.html', {
        'subscription': sub,
        'corporate': corp,
    })


@login_required
@require_POST
def cancel_subscription_view(request):
    if cancel_subscription(request.user):
        messages.success(request, _('Obuna bekor qilindi.'))
    else:
        messages.info(request, _('Faol shaxsiy obuna topilmadi.'))
    return redirect('movie:my_subscription')


@login_required
def subscribe(request):
    if user_has_subscription(request.user):
        return redirect('movie:my_subscription')

    corporate_plans = SubscriptionPlan.objects.filter(
        is_active=True, is_corporate=True,
    ).order_by('order', 'price')
    individual_plans = SubscriptionPlan.objects.filter(
        is_active=True, is_corporate=False,
    ).order_by('order', 'price')

    if not corporate_plans.exists() and not individual_plans.exists():
        return render(request, 'subscription/no_plan.html')

    ctx = _payment_context()
    ctx.update({
        'corporate_plans': corporate_plans,
        'individual_plans': individual_plans,
    })
    return render(request, 'subscription/subscribe.html', ctx)


@login_required
def corporate_request(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True, is_corporate=True)

    if request.method == 'POST':
        form = CorporateRequestForm(request.POST, plan=plan)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.plan = plan
            obj.user = request.user
            obj.save()
            messages.success(request, _('Korporativ so\'rovingiz qabul qilindi. Tez orada bog\'lanamiz!'))
            return redirect('movie:my_subscription')
    else:
        initial = {}
        if request.user.email:
            initial['email'] = request.user.email
        initial['contact_name'] = request.user.get_full_name() or request.user.username
        form = CorporateRequestForm(initial=initial, plan=plan)

    return render(request, 'subscription/corporate_request.html', {
        'form': form,
        'plan': plan,
    })


@login_required
def subscription_plans(request):
    return redirect('movie:subscribe')


@login_required
@require_POST
def checkout(request):
    plan_id = request.POST.get('plan_id')
    provider = request.POST.get('provider')

    plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True, is_corporate=False)

    if provider == PaymentOrder.PROVIDER_CLICK:
        if not click_configured():
            return render(request, 'subscription/payment_fail.html', {
                'message': _('Click to\'lov tizimi sozlanmagan. Admin bilan bog\'laning.'),
            })
    elif provider == PaymentOrder.PROVIDER_PAYME:
        if not payme_configured():
            return render(request, 'subscription/payment_fail.html', {
                'message': _('Payme to\'lov tizimi sozlanmagan. Admin bilan bog\'laning.'),
            })
    else:
        return HttpResponseBadRequest('Invalid provider')

    order = PaymentOrder.objects.create(
        user=request.user,
        order_type=PaymentOrder.ORDER_SUBSCRIPTION,
        plan=plan,
        provider=provider,
        amount=plan.price,
    )

    if provider == PaymentOrder.PROVIDER_CLICK:
        return redirect(get_click_payment_url(order, request))
    return redirect(get_payme_checkout_url(order, request))


@login_required
def payment_success(request):
    return render(request, 'subscription/payment_success.html', {
        'has_subscription': user_has_subscription(request.user),
    })


@login_required
def payment_fail(request):
    return render(request, 'subscription/payment_fail.html', {
        'message': request.GET.get('message', ''),
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def click_callback(request):
    params = request.GET if request.method == 'GET' else request.POST
    data = {k: params.get(k, '') for k in params.keys()}
    action = int(data.get('action', -1))

    if action == 0:
        result = handle_click_prepare(data)
    elif action == 1:
        result = handle_click_complete(data)
    else:
        result = {'error': -3, 'error_note': 'Invalid action'}

    return JsonResponse(result)


@csrf_exempt
@require_POST
def payme_callback(request):
    result = handle_payme_request(request)
    return JsonResponse(result)


@login_required
@require_POST
def test_subscribe(request):
    if not test_mode_available():
        return HttpResponseBadRequest('Test mode disabled')

    plan = get_object_or_404(
        SubscriptionPlan,
        pk=request.POST.get('plan_id'),
        is_active=True,
        is_corporate=False,
    )
    order = PaymentOrder.objects.create(
        user=request.user,
        order_type=PaymentOrder.ORDER_SUBSCRIPTION,
        plan=plan,
        provider=PaymentOrder.PROVIDER_TEST,
        amount=plan.price,
    )
    _mark_order_paid(order, 'test')
    messages.success(request, _('Sinov obunasi faollashtirildi!'))
    return redirect('movie:payment_success')
