
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.generic import RedirectView

# from django.contrib.auth.views import LoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'accounts/login/',
        RedirectView.as_view(url='/login/', query_string=True, permanent=False),
    ),
    path('i18n/', include('django.conf.urls.i18n')),
    path('oauth/', include('social_django.urls', namespace='social')),
    path("", include('movie.urls', namespace='movie')),
    path('', include('django.contrib.auth.urls')),
    # path('__debug__/', include('debug_toolbar.urls')),
    # Login
    # path("login/", LoginView.as_view(
    #     template_name=''
    # ),)
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Posterlar — media/ gitdan keladi (Render va lokal)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
