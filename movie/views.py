import json
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect ,HttpResponse, JsonResponse
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.views.generic.edit import FormMixin
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from transliterate import translit
from django.utils.translation import gettext as _
from django.utils.translation import get_language

from .models import *
from .stream_utils import server_watermark_enabled
from .forms import UserRegisterForm, CommentForm
from .login_throttle import clear_login_attempts, login_lock_status, record_failed_login
from .translations import translate_category
from .utils import (
    try_apply_pending_referral,
    user_can_watch_live,
    user_can_watch_movie,
    user_can_watch_movies,
    user_has_subscription,
    get_corporate_membership,
    get_movie_share_access,
    get_or_create_movie_share_link,
    is_share_only_viewer,
    mark_share_session_registered,
    share_guest_preview_expired,
    share_guest_preview_remaining,
)


def _viewer_subscriber_code(user):
    if not user.is_authenticated:
        return ''
    profile = getattr(user, 'profile', None)
    if profile is None:
        profile, _ = UserProfile.objects.get_or_create(user=user)
    elif not profile.subscriber_code:
        if profile.ensure_subscriber_code():
            profile.save(update_fields=['subscriber_code'])
    return profile.subscriber_code


def category_list(request, slug):
    if slug == 'teleperedachi':
        return channel_list(request)
    category = get_object_or_404(Category, slug=slug)
    subcategories = Category.objects.filter(parent=category, is_active=True).order_by('order', 'name')
    movies = Movie.objects.filter(category=category)
    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    lang = get_language() or 'ru'
    return render(request, 'list.html', {
        'page_obj': page_obj,
        'cat_name': translate_category(category, lang),
        'category': category,
        'subcategories': [
            {'obj': sub, 'name': translate_category(sub, lang)}
            for sub in subcategories
        ],
    })

def my_login(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    locked, lock_remaining = login_lock_status(request)
    if request.method == 'POST':
        if locked:
            minutes = max(1, (lock_remaining + 59) // 60)
            messages.error(
                request,
                _("Juda ko'p noto'g'ri urinish. %(minutes)s daqiqadan keyin qayta urinib ko'ring.")
                % {'minutes': minutes},
            )
        else:
            username = request.POST.get("username")
            password = request.POST.get("password")
            user = authenticate(request, username=username, password=password)
            if user is not None:
                clear_login_attempts(request)
                login(request, user)
                mark_share_session_registered(request)
                if user.is_staff:
                    return HttpResponseRedirect("/panel/")
                if request.session.get('corporate_movie_share') and next_url.startswith('/'):
                    return HttpResponseRedirect(next_url)
                if try_apply_pending_referral(request):
                    return HttpResponseRedirect("/my-subscription/")
                if next_url.startswith('/'):
                    return HttpResponseRedirect(next_url)
                return HttpResponseRedirect("/")
            just_locked = record_failed_login(request)
            if just_locked:
                messages.error(
                    request,
                    _("5 marta noto'g'ri parol kiritildi. Hisobingiz 5 daqiqaga bloklandi."),
                )
                locked, lock_remaining = True, 300
            else:
                messages.error(request, _("Неверный логин или пароль"))
    locked, lock_remaining = login_lock_status(request)
    return render(request, "registration/login.html", {
        'next': next_url,
        'login_locked': locked,
        'lock_remaining': lock_remaining,
    })

def logout_view(request):
    logout(request)
    messages.info(request, _("Вы вышли из аккаунта"))
    return HttpResponseRedirect("/")

def registration_view(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.phone = form.cleaned_data.get('phone', '').strip()
            profile.save(update_fields=['phone'])
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            mark_share_session_registered(request)
            messages.success(request, _("Ro'yxatdan muvaffaqiyatli o'tdingiz!"))
            if request.session.get('corporate_movie_share') and next_url.startswith('/'):
                return HttpResponseRedirect(next_url)
            if try_apply_pending_referral(request):
                return HttpResponseRedirect("/my-subscription/")
            if next_url.startswith('/'):
                return HttpResponseRedirect(next_url)
            return HttpResponseRedirect("/")
        messages.error(request, _("Ro'yxatdan o'tishda xato. Quyidagi maydonlarni tekshiring."))
    else:
        form = UserRegisterForm()
    return render(request, "registration/registration.html", {"form": form, "next": next_url})


class HomeView(ListView):
    model = Movie
    template_name = 'index.html'

class MovieDetailView(FormMixin,DetailView):
    model = Movie
    template_name = 'movie-detail.html'
    form_class = CommentForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        has_access = user_can_watch_movie(user, self.object, self.request)
        context['has_access'] = has_access
        context['can_watch'] = has_access
        context['is_authenticated'] = user.is_authenticated
        context['has_trailer'] = self.object.has_trailer()
        context['trailer_stream_url'] = self.object.get_trailer_stream_path()
        context['is_share_link_viewer'] = is_share_only_viewer(self.request, self.object, user)
        context['share_requires_registration'] = bool(
            is_share_only_viewer(self.request, self.object, user)
            and not user.is_authenticated
            and share_guest_preview_expired(self.request, self.object)
        )
        remaining = share_guest_preview_remaining(self.request, self.object)
        context['share_preview_seconds'] = remaining if remaining is not None else 0
        context['is_guest_movie_share'] = context['is_share_link_viewer']
        corp = get_corporate_membership(user) if user.is_authenticated else None
        context['corporate_movie_share_url'] = ''
        if corp and user_can_watch_movies(user):
            link = get_or_create_movie_share_link(corp, self.object)
            context['corporate_movie_share_url'] = self.request.build_absolute_uri(
                reverse('movie:corporate_movie_share', kwargs={'token': link.token}),
            )
        if has_access:
            viewer_code = _viewer_subscriber_code(user) if user.is_authenticated else ''
            context['video_streams_json'] = json.dumps(
                self.object.get_protected_streams_dict(user=user, request=self.request),
            )
            context['viewer_watermark'] = viewer_code
            context['server_watermark_burn'] = server_watermark_enabled() and bool(viewer_code)
            context['movie_uid'] = self.object.movie_uid
        else:
            context['video_streams_json'] = '{}'
            context['viewer_watermark'] = ''
            context['server_watermark_burn'] = False
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()       
        form = self.get_form()
        if form.is_valid():          
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    # @staticmethod
    def get_success_url(self):
        return reverse_lazy("movie:detail", kwargs={"slug":self.object.slug})

    def form_valid(self, form):
        f = form.save(commit=False)
        f.movie = self.object
        f.save()
        return super().form_valid(form)


def search(request):
    q = (request.GET.get("query") or "").strip()
    if not q:
        return render(request, 'search_list.html', {"object_list": []})

    try:
        ru_text = translit(q, "ru").title()
    except Exception:
        ru_text = q

    data = Movie.objects.filter(
        Q(title__icontains=q) | Q(title_uz__icontains=q) | Q(title_en__icontains=q)
        | Q(title__icontains=ru_text) | Q(actors__name__icontains=ru_text)
        | Q(genres__name__icontains=ru_text)
    ).distinct()

    return render(request, 'search_list.html', {"object_list": data})

def movie_sorting(request, sort_params):
    # sort_params.split("=")[0] sort type 
    # sort_params.split("=")[1] sort value
    sort_type = sort_params.split("=")[0]
    sort_value = sort_params.split("=")[1]
    # print(sort_type)
    # print(sort_params)
    if sort_type == "genres":
        genre = Genre.objects.get(id=sort_value)
        object_list = Movie.objects.filter(genres=sort_value)
        return render(request, "index.html", {"object_list":object_list, "filter_category":genre.name})
    elif sort_type == "year":
        object_list = Movie.objects.filter(year=sort_value)
        return render(request, "index.html", {"object_list":object_list, "filter_category":sort_value})
    elif sort_type == "quality":
        object_list = Movie.objects.filter(quality=sort_value)
        return render(request, "index.html", {"object_list":object_list, "filter_category":sort_value})
    else:
        print("ERROR" * 10)
        return HttpResponseRedirect("/")
    


def likeMovie(request):
    if request.user.is_authenticated:
        print(request.GET.get("data"))
    else:
        return JsonResponse({"status":400})
    return JsonResponse({"status":200})

def likedMovies(request):
    return render(request, "liked-movies.html")


def live_list(request):
    streams = LiveStream.objects.filter(is_active=True).order_by('-is_live', '-created_at')
    return render(request, 'live_list.html', {'streams': streams})


def live_watch(request, slug):
    stream = get_object_or_404(LiveStream, slug=slug, is_active=True)
    user = request.user
    has_access = user_can_watch_live(user)
    return render(request, 'live_watch.html', {
        'stream': stream,
        'has_access': has_access,
        'viewer_watermark': _viewer_subscriber_code(user) if has_access else '',
    })


def channel_list(request):
    from django.contrib import messages
    from django.core.paginator import Paginator
    from django.utils.translation import get_language

    from .iptv_channels import sync_country_channels
    from .iptv_countries import (
        PRIMARY_COUNTRY,
        build_country_nav,
        country_label,
        get_country_codes,
        popular_country_nav,
    )

    lang = get_language() or 'uz'
    all_codes = set(get_country_codes())
    active_country = (request.GET.get('country') or PRIMARY_COUNTRY).lower()
    if active_country not in all_codes:
        active_country = PRIMARY_COUNTRY

    if not TvChannel.objects.filter(is_active=True, country_code=active_country).exists():
        if active_country in all_codes:
            try:
                result = sync_country_channels(active_country)
                if result['total']:
                    messages.success(
                        request,
                        f"{country_label(active_country, lang)}: {result['total']} ta kanal yuklandi.",
                    )
            except (FileNotFoundError, OSError) as exc:
                messages.error(request, f"Kanallar yuklanmadi: {exc}")

    channels_qs = TvChannel.objects.filter(is_active=True, country_code=active_country).order_by('order', 'name')
    paginator = Paginator(channels_qs, 48)
    page_obj = paginator.get_page(request.GET.get('page'))
    active_qs = TvChannel.objects.filter(is_active=True)

    return render(request, 'channel_list.html', {
        'page_obj': page_obj,
        'channels': page_obj.object_list,
        'active_country': active_country,
        'country_label': country_label(active_country, lang),
        'country_nav': build_country_nav(active_qs, lang, include_empty=True),
        'popular_countries': popular_country_nav(lang, active_qs),
    })


def channel_watch(request, slug):
    channel = get_object_or_404(TvChannel, slug=slug, is_active=True)
    return render(request, 'channel_watch.html', {'channel': channel})
