import json
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
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
from .forms import UserRegisterForm, CommentForm
from .translations import translate_category
from .utils import user_can_watch_live, user_can_watch_movies, user_has_subscription


def category_list(request, slug):
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
    if request.method == 'POST':
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_staff:
                return HttpResponseRedirect("/panel/")
            if next_url.startswith('/'):
                return HttpResponseRedirect(next_url)
            return HttpResponseRedirect("/")
        messages.error(request, _("Неверный логин или пароль"))
    return render(request, "registration/login.html", {'next': next_url})

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
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, _("Ro'yxatdan muvaffaqiyatli o'tdingiz!"))
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
        has_access = user_can_watch_movies(user)
        context['has_access'] = has_access
        context['can_watch'] = has_access
        context['is_authenticated'] = user.is_authenticated
        if has_access:
            context['video_streams_json'] = json.dumps(self.object.get_protected_streams_dict())
        else:
            context['video_streams_json'] = '{}'
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
    has_access = user_can_watch_live(request.user)
    return render(request, 'live_watch.html', {
        'stream': stream,
        'has_access': has_access,
    })
