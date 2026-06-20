from datetime import timedelta

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import OperationalError
from django.db.models import Count, Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .decorators import admin_required
from .forms import (
    APIPartnerForm, CategoryForm, CorporateMemberForm, LiveStreamForm, MovieForm,
    PaymentSettingsForm, SubscriptionForm, SubscriptionPlanForm, SiteSettingsForm, TicketEventForm,
)
from .payment_config import click_configured, payme_configured
from .models import (
    APIAccessLog, APIPartner, Category, Comment, CorporateMember, CorporateOrganization,
    CorporateSubscriptionRequest, Genre, LiveStream, Movie, MovieStream,
    PaymentSettings, PiracyAlert, PurchasedTicket, SubscriptionPlan, SiteSettings, HomePremiere, TelegramChannelVideo,
    TicketEvent,
    UserProfile, UserSubscription, WatchHistory,
)
from .telegram_storage import telegram_configured
from .utils import approve_corporate_request


def _movie_form_context(form, title, movie=None):
    return {
        'form': form,
        'title': title,
        'movie': movie,
        'telegram_configured': telegram_configured(),
        'telegram_videos': TelegramChannelVideo.objects.filter(
            linked_stream__isnull=True,
        ).order_by('-created_at')[:200],
        'stream_qualities': ['480', '720', '1080', '4k'],
    }


def _live_stream_stats():
    try:
        return (
            LiveStream.objects.filter(is_active=True).count(),
            LiveStream.objects.filter(is_active=True, is_live=True).count(),
        )
    except OperationalError:
        return 0, 0


@admin_required
def dashboard(request):
    now = timezone.now()
    active_subs = UserSubscription.objects.filter(is_active=True, end_date__gt=now)
    total_live_streams, live_now = _live_stream_stats()
    context = {
        'total_users': User.objects.count(),
        'total_movies': Movie.objects.count(),
        'total_comments': Comment.objects.count(),
        'total_categories': Category.objects.count(),
        'total_live_streams': total_live_streams,
        'live_now': live_now,
        'active_subscribers': active_subs.count(),
        'total_revenue': active_subs.aggregate(total=Sum('payment_amount'))['total'] or 0,
        'recent_users': User.objects.order_by('-date_joined')[:8],
        'recent_movies': Movie.objects.order_by('-id')[:8],
        'recent_subscriptions': UserSubscription.objects.select_related('user', 'plan')[:8],
        'top_movies': Movie.objects.order_by('-likes')[:5],
    }
    return render(request, 'admin_panel/dashboard.html', context)


@admin_required
def category_list(request):
    parents = Category.objects.filter(parent__isnull=True).annotate(
        movie_count=Count('movie_category'),
    ).prefetch_related('children').order_by('order', 'name')
    return render(request, 'admin_panel/category_list.html', {'parents': parents})


@admin_required
def category_add(request):
    parent = None
    parent_id = request.GET.get('parent') or request.POST.get('parent')
    if parent_id:
        parent = get_object_or_404(Category, pk=parent_id, parent__isnull=True)

    if request.method == 'POST':
        form = CategoryForm(request.POST, fixed_parent=parent)
        if form.is_valid():
            cat = form.save()
            messages.success(request, _('Раздел добавлен!'))
            if cat.parent_id:
                return redirect('movie:admin_category_edit', pk=cat.parent_id)
            return redirect('movie:admin_category_list')
    else:
        form = CategoryForm(fixed_parent=parent)

    title = _('Ichki bo\'lim qo\'shish') if parent else _('Добавить раздел')
    return render(request, 'admin_panel/category_form.html', {
        'form': form,
        'title': title,
        'parent': parent,
    })


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    children = category.children.annotate(movie_count=Count('movie_category')).order_by('order', 'name')
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, _('Раздел обновлён!'))
            return redirect('movie:admin_category_edit', pk=category.pk)
    else:
        form = CategoryForm(instance=category)
    return render(request, 'admin_panel/category_form.html', {
        'form': form,
        'title': _('Редактировать раздел'),
        'category': category,
        'children': children,
    })


@admin_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    has_movies = category.movie_category.exists()
    has_children = category.children.exists()
    if request.method == 'POST':
        if has_movies:
            messages.error(request, _('Нельзя удалить: в разделе есть фильмы!'))
        elif has_children:
            messages.error(request, _('Нельзя удалить: ichki bo\'limlar mavjud!'))
        else:
            parent_pk = category.parent_id
            category.delete()
            messages.success(request, _('Раздел удалён!'))
            if parent_pk:
                return redirect('movie:admin_category_edit', pk=parent_pk)
            return redirect('movie:admin_category_list')
        if category.parent_id:
            return redirect('movie:admin_category_edit', pk=category.parent_id)
        return redirect('movie:admin_category_list')
    return render(request, 'admin_panel/category_delete.html', {
        'category': category,
        'has_movies': has_movies,
        'has_children': has_children,
    })


@admin_required
def movie_list(request):
    movies = Movie.objects.select_related('category').annotate(
        comment_count=Count('movie_comments')
    ).order_by('-id')
    q = request.GET.get('q', '')
    if q:
        movies = movies.filter(title__icontains=q)
    paginator = Paginator(movies, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/movie_list.html', {'page_obj': page_obj, 'q': q})


@admin_required
def movie_add(request):
    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            for warning in getattr(form, 'telegram_warnings', []):
                messages.warning(request, warning)
            messages.success(request, _('Фильм успешно добавлен!'))
            return redirect('movie:admin_movie_list')
    else:
        form = MovieForm()
    return render(request, 'admin_panel/movie_form.html', _movie_form_context(form, _('Добавить фильм')))


@admin_required
def movie_edit(request, pk):
    movie = get_object_or_404(Movie, pk=pk)
    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES, instance=movie)
        if form.is_valid():
            form.save()
            for warning in getattr(form, 'telegram_warnings', []):
                messages.warning(request, warning)
            messages.success(request, _('Фильм обновлён!'))
            return redirect('movie:admin_movie_list')
    else:
        form = MovieForm(instance=movie)
    changed = movie.ensure_protection_ids()
    if changed:
        movie.save(update_fields=changed)
    return render(request, 'admin_panel/movie_form.html', _movie_form_context(form, _('Редактировать фильм'), movie))


@admin_required
def telegram_video_list(request):
    videos = TelegramChannelVideo.objects.select_related('linked_stream__movie').order_by('-created_at')
    q = request.GET.get('q', '')
    if q:
        videos = videos.filter(
            Q(file_name__icontains=q) | Q(caption__icontains=q) | Q(file_unique_id__icontains=q),
        )
    status = request.GET.get('status', 'all')
    if status == 'free':
        videos = videos.filter(linked_stream__isnull=True)
    elif status == 'linked':
        videos = videos.filter(linked_stream__isnull=False)
    paginator = Paginator(videos, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    from .telegram_storage import get_telegram_admin_ids
    return render(request, 'admin_panel/telegram_video_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status': status,
        'telegram_configured': telegram_configured(),
        'telegram_admin_ids': get_telegram_admin_ids(),
    })


@admin_required
def telegram_video_link(request, pk):
    video = get_object_or_404(TelegramChannelVideo, pk=pk)
    if video.linked_stream_id:
        messages.error(request, _('Bu video allaqachon filmga bog\'langan.'))
        return redirect('movie:admin_telegram_videos')

    movies = Movie.objects.order_by('-id')
    movie_q = request.GET.get('movie_q', '') or request.POST.get('movie_q', '')
    if movie_q:
        movies = movies.filter(title__icontains=movie_q)

    if request.method == 'POST':
        movie_id = request.POST.get('movie_id')
        quality = request.POST.get('quality', '720')
        movie = get_object_or_404(Movie, pk=movie_id)

        if quality == 'trailer':
            movie.trailer_telegram_file_id = video.file_id
            movie.trailer_telegram_file_unique_id = video.file_unique_id
            movie.save(update_fields=[
                'trailer_telegram_file_id',
                'trailer_telegram_file_unique_id',
            ])
            messages.success(
                request,
                _('Treler "%(title)s" filmiga bog\'landi.') % {'title': movie.title},
            )
        else:
            stream, _ = MovieStream.objects.get_or_create(movie=movie, quality=quality)
            stream.telegram_file_id = video.file_id
            stream.telegram_file_unique_id = video.file_unique_id
            stream.url = ''
            stream.save()
            video.linked_stream = stream
            video.save(update_fields=['linked_stream'])
            messages.success(
                request,
                _('%(quality)s video "%(title)s" filmiga bog\'landi.')
                % {'quality': quality, 'title': movie.title},
            )
        return redirect('movie:admin_telegram_videos')

    return render(request, 'admin_panel/telegram_video_link.html', {
        'video': video,
        'movies': movies[:100],
        'movie_q': movie_q,
        'qualities': MovieStream.QUALITY_CHOICES,
    })


@admin_required
def movie_delete(request, pk):
    movie = get_object_or_404(Movie, pk=pk)
    if request.method == 'POST':
        movie.delete()
        messages.success(request, _('Фильм удалён!'))
        return redirect('movie:admin_movie_list')
    return render(request, 'admin_panel/movie_delete.html', {'movie': movie})


@admin_required
def user_list(request):
    users = User.objects.select_related('profile').annotate(
        sub_count=Count('subscriptions'),
        comment_count=Count('subscriptions'),
    ).order_by('-date_joined')
    q = request.GET.get('q', '')
    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(profile__subscriber_code__icontains=q)
            | Q(profile__phone__icontains=q)
        )
    paginator = Paginator(users, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    for u in page_obj:
        profile, _ = UserProfile.objects.get_or_create(user=u)
        u.profile = profile

    now = timezone.now()
    active_user_ids = set(
        UserSubscription.objects.filter(is_active=True, end_date__gt=now).values_list('user_id', flat=True)
    )
    return render(request, 'admin_panel/user_list.html', {
        'page_obj': page_obj,
        'q': q,
        'active_user_ids': active_user_ids,
    })


@admin_required
def watch_history_list(request):
    history = WatchHistory.objects.select_related(
        'user', 'user__profile', 'movie',
    ).order_by('-watched_at')
    q = request.GET.get('q', '')
    if q:
        history = history.filter(
            Q(user__username__icontains=q)
            | Q(user__profile__phone__icontains=q)
            | Q(user__profile__subscriber_code__icontains=q)
            | Q(subscriber_code__icontains=q)
            | Q(movie__title__icontains=q)
            | Q(movie__title_uz__icontains=q)
            | Q(ip_address__icontains=q)
        )
    paginator = Paginator(history, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/watch_history_list.html', {
        'page_obj': page_obj,
        'q': q,
    })


@admin_required
def subscription_list(request):
    now = timezone.now()
    subscriptions = UserSubscription.objects.select_related('user', 'plan').order_by('-start_date')
    status = request.GET.get('status', 'all')
    if status == 'active':
        subscriptions = subscriptions.filter(is_active=True, end_date__gt=now)
    elif status == 'expired':
        subscriptions = subscriptions.filter(Q(end_date__lte=now) | Q(is_active=False))
    paginator = Paginator(subscriptions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/subscription_list.html', {
        'page_obj': page_obj,
        'status': status,
        'plans': SubscriptionPlan.objects.filter(is_active=True),
    })


@admin_required
def subscription_cancel(request, pk):
    sub = get_object_or_404(UserSubscription, pk=pk)
    if request.method == 'POST':
        if sub.is_active:
            sub.is_active = False
            sub.save(update_fields=['is_active'])
            messages.success(request, _('Obuna bekor qilindi: %(user)s') % {'user': sub.user.username})
        else:
            messages.info(request, _('Obuna allaqachon bekor qilingan.'))
        status = request.POST.get('status', 'all')
        page = request.POST.get('page', '')
        url = reverse('movie:admin_subscription_list') + f'?status={status}'
        if page:
            url += f'&page={page}'
        return redirect(url)
    return redirect('movie:admin_subscription_list')


@admin_required
def subscription_add(request):
    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            sub = form.save(commit=False)
            if not sub.start_date:
                sub.start_date = timezone.now()
            sub.save()
            messages.success(request, _('Подписка добавлена!'))
            return redirect('movie:admin_subscription_list')
    else:
        form = SubscriptionForm(initial={
            'end_date': timezone.now() + timedelta(days=30),
            'is_active': True,
        })
    return render(request, 'admin_panel/subscription_form.html', {'form': form, 'title': _('Добавить подписку')})


@admin_required
def plan_list(request):
    plans = SubscriptionPlan.objects.annotate(
        subscriber_count=Count('subscribers'),
    ).order_by('-is_corporate', 'order', 'price')
    return render(request, 'admin_panel/plan_list.html', {'plans': plans})


@admin_required
def live_list(request):
    streams = LiveStream.objects.order_by('-is_live', '-created_at')
    q = request.GET.get('q', '')
    if q:
        streams = streams.filter(title__icontains=q)
    paginator = Paginator(streams, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/live_list.html', {'page_obj': page_obj, 'q': q})


@admin_required
def live_add(request):
    if request.method == 'POST':
        form = LiveStreamForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Прямой эфир добавлен!'))
            return redirect('movie:admin_live_list')
    else:
        form = LiveStreamForm()
    return render(request, 'admin_panel/live_form.html', {'form': form, 'title': _('Добавить прямой эфир')})


@admin_required
def live_edit(request, pk):
    stream = get_object_or_404(LiveStream, pk=pk)
    if request.method == 'POST':
        form = LiveStreamForm(request.POST, request.FILES, instance=stream)
        if form.is_valid():
            form.save()
            messages.success(request, _('Прямой эфир обновлён!'))
            return redirect('movie:admin_live_list')
    else:
        form = LiveStreamForm(instance=stream)
    return render(request, 'admin_panel/live_form.html', {'form': form, 'title': _('Редактировать прямой эфир'), 'stream': stream})


@admin_required
def live_delete(request, pk):
    stream = get_object_or_404(LiveStream, pk=pk)
    if request.method == 'POST':
        stream.delete()
        messages.success(request, _('Прямой эфир удалён!'))
        return redirect('movie:admin_live_list')
    return render(request, 'admin_panel/live_delete.html', {'stream': stream})


@admin_required
def plan_add(request):
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Тариф добавлен!'))
            return redirect('movie:admin_plan_list')
    else:
        form = SubscriptionPlanForm()
    return render(request, 'admin_panel/plan_form.html', {'form': form, 'title': _('Добавить тариф')})


@admin_required
def plan_edit(request, pk):
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, _('Тариф обновлён!'))
            return redirect('movie:admin_plan_list')
    else:
        form = SubscriptionPlanForm(instance=plan)
    return render(request, 'admin_panel/plan_form.html', {
        'form': form,
        'title': _('Редактировать тариф'),
        'plan': plan,
    })


@admin_required
def payment_settings(request):
    ps = PaymentSettings.load()
    if request.method == 'POST':
        form = PaymentSettingsForm(request.POST, instance=ps)
        if form.is_valid():
            form.save()
            messages.success(request, _('To\'lov sozlamalari saqlandi!'))
            return redirect('movie:admin_payment_settings')
    else:
        form = PaymentSettingsForm(instance=ps)
    return render(request, 'admin_panel/payment_settings.html', {
        'form': form,
        'click_ready': click_configured(),
        'payme_ready': payme_configured(),
    })


@admin_required
def site_settings(request):
    settings_obj = SiteSettings.load()
    premieres = HomePremiere.objects.select_related('movie').order_by('order', 'id')

    if request.method == 'POST':
        action = request.POST.get('action', 'save_settings')

        if action == 'add_premiere':
            movie_id = request.POST.get('movie_id')
            movie = Movie.objects.filter(pk=movie_id).first()
            if not movie:
                messages.error(request, _('Kino topilmadi.'))
            elif HomePremiere.objects.filter(movie=movie).exists():
                messages.error(request, _('Bu kino allaqachon premyeralarda.'))
            else:
                next_order = (
                    HomePremiere.objects.order_by('-order').values_list('order', flat=True).first() or 0
                ) + 1
                HomePremiere.objects.create(movie=movie, order=next_order, is_active=True)
                messages.success(request, _('Premyera qo\'shildi: %(title)s') % {'title': movie.title})
            return redirect('movie:admin_site_settings')

        if action == 'delete_premiere':
            HomePremiere.objects.filter(pk=request.POST.get('premiere_id')).delete()
            messages.success(request, _('Premyera o\'chirildi.'))
            return redirect('movie:admin_site_settings')

        if action == 'save_order':
            for premiere in premieres:
                key = f'order_{premiere.pk}'
                if key in request.POST:
                    try:
                        premiere.order = max(0, int(request.POST.get(key, premiere.order)))
                        premiere.is_active = request.POST.get(f'active_{premiere.pk}') == 'on'
                        premiere.save(update_fields=['order', 'is_active'])
                    except ValueError:
                        pass
            messages.success(request, _('Premyera navbati saqlandi.'))
            return redirect('movie:admin_site_settings')

        form = SiteSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, _('Sayt sozlamalari saqlandi!'))
            return redirect('movie:admin_site_settings')
    else:
        form = SiteSettingsForm(instance=settings_obj)

    used_ids = set(HomePremiere.objects.values_list('movie_id', flat=True))
    available_movies = Movie.objects.exclude(pk__in=used_ids).order_by('-created_at')[:200]

    return render(request, 'admin_panel/site_settings.html', {
        'form': form,
        'premieres': HomePremiere.objects.select_related('movie').order_by('order', 'id'),
        'available_movies': available_movies,
        'settings_obj': settings_obj,
    })


@admin_required
def plan_delete(request, pk):
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    has_subscribers = plan.subscribers.filter(is_active=True).exists()
    if request.method == 'POST':
        if has_subscribers:
            messages.error(request, _('Bu tarifda faol obunachilar bor — o\'chirib bo\'lmaydi.'))
        else:
            plan.delete()
            messages.success(request, _('Тариф удалён!'))
        return redirect('movie:admin_plan_list')
    return render(request, 'admin_panel/plan_delete.html', {
        'plan': plan,
        'has_subscribers': has_subscribers,
    })


@admin_required
def corporate_request_list(request):
    status = request.GET.get('status', 'pending')
    requests_qs = CorporateSubscriptionRequest.objects.select_related('plan', 'user')
    if status == 'pending':
        requests_qs = requests_qs.filter(status=CorporateSubscriptionRequest.STATUS_PENDING)
    elif status == 'approved':
        requests_qs = requests_qs.filter(status=CorporateSubscriptionRequest.STATUS_APPROVED)
    elif status == 'rejected':
        requests_qs = requests_qs.filter(status=CorporateSubscriptionRequest.STATUS_REJECTED)
    paginator = Paginator(requests_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/corporate_request_list.html', {
        'page_obj': page_obj,
        'status': status,
        'pending_count': CorporateSubscriptionRequest.objects.filter(
            status=CorporateSubscriptionRequest.STATUS_PENDING,
        ).count(),
    })


@admin_required
@require_POST
def corporate_request_approve(request, pk):
    req = get_object_or_404(CorporateSubscriptionRequest, pk=pk)
    if req.status != CorporateSubscriptionRequest.STATUS_PENDING:
        messages.error(request, _('Bu so\'rov allaqachon ko\'rib chiqilgan.'))
    else:
        org = approve_corporate_request(req)
        messages.success(request, _('Korporativ obuna tasdiqlandi: %s') % org.company_name)
    return redirect('movie:admin_corporate_requests')


@admin_required
def corporate_request_reject(request, pk):
    req = get_object_or_404(CorporateSubscriptionRequest, pk=pk)
    if request.method == 'POST':
        req.status = CorporateSubscriptionRequest.STATUS_REJECTED
        req.admin_note = request.POST.get('admin_note', '')
        req.processed_at = timezone.now()
        req.save(update_fields=['status', 'admin_note', 'processed_at'])
        messages.success(request, _('So\'rov rad etildi.'))
        return redirect('movie:admin_corporate_requests')
    return render(request, 'admin_panel/corporate_request_reject.html', {'req': req})


@admin_required
def corporate_org_list(request):
    orgs = CorporateOrganization.objects.select_related('plan', 'admin_user').annotate(
        member_count=Count('members'),
    ).order_by('-created_at')
    paginator = Paginator(orgs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/corporate_org_list.html', {'page_obj': page_obj})


@admin_required
def corporate_org_members(request, pk):
    org = get_object_or_404(CorporateOrganization, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            form = CorporateMemberForm(request.POST, organization=org)
            if form.is_valid():
                if org.seats_available <= 0:
                    messages.error(request, _('Barcha o\'rinlar band.'))
                else:
                    CorporateMember.objects.create(
                        organization=org,
                        user=form.cleaned_data['user'],
                    )
                    messages.success(request, _('A\'zo qo\'shildi.'))
                return redirect('movie:admin_corporate_org_members', pk=pk)
        elif action == 'remove':
            member_id = request.POST.get('member_id')
            CorporateMember.objects.filter(pk=member_id, organization=org).delete()
            messages.success(request, _('A\'zo o\'chirildi.'))
            return redirect('movie:admin_corporate_org_members', pk=pk)
    else:
        form = CorporateMemberForm(organization=org)
    members = list(
        org.members.select_related('user').annotate(
            ref_count=Count('referrals'),
        ).order_by('-added_at')
    )
    for m in members:
        m.referral_full_url = request.build_absolute_uri(m.get_referral_path())
    return render(request, 'admin_panel/corporate_org_members.html', {
        'org': org,
        'members': members,
        'form': form,
    })


@admin_required
def ticket_list(request):
    events = TicketEvent.objects.select_related('category').order_by('-event_date')
    q = request.GET.get('q', '')
    cat = request.GET.get('category', '')
    if q:
        events = events.filter(title__icontains=q)
    if cat:
        events = events.filter(category__slug=cat)
    paginator = Paginator(events, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/ticket_list.html', {
        'page_obj': page_obj, 'q': q, 'cat': cat,
    })


@admin_required
def ticket_add(request):
    if request.method == 'POST':
        form = TicketEventForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Tadbir qo\'shildi!'))
            return redirect('movie:admin_ticket_list')
    else:
        form = TicketEventForm()
    return render(request, 'admin_panel/ticket_form.html', {
        'form': form, 'title': _('Tadbir qo\'shish'),
    })


@admin_required
def ticket_edit(request, pk):
    event = get_object_or_404(TicketEvent, pk=pk)
    if request.method == 'POST':
        form = TicketEventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, _('Tadbir yangilandi!'))
            return redirect('movie:admin_ticket_list')
    else:
        form = TicketEventForm(instance=event)
    return render(request, 'admin_panel/ticket_form.html', {
        'form': form, 'title': _('Tadbirni tahrirlash'), 'event': event,
    })


@admin_required
def ticket_delete(request, pk):
    event = get_object_or_404(TicketEvent, pk=pk)
    if request.method == 'POST':
        event.delete()
        messages.success(request, _('Tadbir o\'chirildi!'))
        return redirect('movie:admin_ticket_list')
    return render(request, 'admin_panel/ticket_delete.html', {'event': event})


@admin_required
def ticket_sales(request):
    tickets = PurchasedTicket.objects.select_related(
        'user', 'event', 'event__category',
    ).order_by('-created_at')
    paginator = Paginator(tickets, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/ticket_sales.html', {'page_obj': page_obj})


@admin_required
def api_partner_list(request):
    partners = APIPartner.objects.order_by('-created_at')
    paginator = Paginator(partners, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/api_partner_list.html', {'page_obj': page_obj})


@admin_required
def api_partner_add(request):
    if request.method == 'POST':
        form = APIPartnerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('API hamkor qo\'shildi!'))
            return redirect('movie:admin_api_partners')
    else:
        form = APIPartnerForm()
    return render(request, 'admin_panel/api_partner_form.html', {
        'form': form, 'title': _('API hamkor qo\'shish'),
    })


@admin_required
def piracy_alert_list(request):
    alerts = PiracyAlert.objects.select_related('movie').order_by('-created_at')
    status = request.GET.get('status', '')
    if status:
        alerts = alerts.filter(status=status)
    paginator = Paginator(alerts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/piracy_alert_list.html', {
        'page_obj': page_obj, 'status': status,
        'new_count': PiracyAlert.objects.filter(status=PiracyAlert.STATUS_NEW).count(),
    })


@admin_required
@require_POST
def piracy_alert_resolve(request, pk):
    alert = get_object_or_404(PiracyAlert, pk=pk)
    alert.status = PiracyAlert.STATUS_RESOLVED
    alert.save(update_fields=['status'])
    messages.success(request, _('Ogohlantirish hal qilindi.'))
    return redirect('movie:admin_piracy_alerts')


@admin_required
def content_protection(request):
    return render(request, 'admin_panel/content_protection.html', {
        'movies_protected': Movie.objects.exclude(movie_uid='').count(),
        'partners_count': APIPartner.objects.filter(is_active=True).count(),
        'alerts_new': PiracyAlert.objects.filter(status=PiracyAlert.STATUS_NEW).count(),
        'subscribers_with_code': UserProfile.objects.exclude(subscriber_code='').count(),
        'recent_logs': APIAccessLog.objects.select_related('partner').order_by('-created_at')[:10],
    })
