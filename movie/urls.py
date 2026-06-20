from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from . import views
from . import admin_views
from . import payment_views
from . import stream_views
from . import ticket_views
from . import corporate_views
from . import api_views
from . import channel_stream
from . import telegram_webhook

app_name= 'movie'

urlpatterns = [
    path("", views.HomeView.as_view(), name='home'),
    path("category/<slug>", views.category_list, name='category_list'),
    path("movie/<slug:slug>/", views.MovieDetailView.as_view(), name='detail'),
    path("search/", views.search, name='search'),
    path("janr/", views.genre_index, name='genre_index'),
    path("janr/<slug:slug>/", views.genre_list, name='genre_list'),
    path("liked/", views.likedMovies, name='likedMovies'),
    path("like/", views.likeMovie, name='likeMovie'),
    path("live/", views.live_list, name='live_list'),
    path("live/<slug:slug>/", views.live_watch, name='live_watch'),
    path("telekanallar/", views.channel_list, name='channel_list'),
    path("telekanallar/<slug:slug>/playlist.m3u8", channel_stream.channel_playlist, name='channel_playlist'),
    path("telekanallar/<slug:slug>/segment/", channel_stream.channel_segment, name='channel_segment'),
    path("telekanallar/<slug:slug>/", views.channel_watch, name='channel_watch'),

    path("tickets/", ticket_views.ticket_home, name='ticket_home'),
    path("tickets/my/", ticket_views.my_tickets, name='my_tickets'),
    path("tickets/success/", ticket_views.ticket_payment_success, name='ticket_payment_success'),
    path("tickets/checkout/", ticket_views.ticket_checkout, name='ticket_checkout'),
    path("tickets/test/", ticket_views.test_ticket_purchase, name='test_ticket_purchase'),
    path("tickets/<slug:slug>/", ticket_views.ticket_category, name='ticket_category'),
    path("tickets/event/<slug:slug>/", ticket_views.ticket_detail, name='ticket_detail'),

    path("subscribe/", payment_views.subscribe, name='subscribe'),
    path("subscribe/corporate/<int:plan_id>/", payment_views.corporate_request, name='corporate_request'),
    path("corporate/join/<str:code>/", corporate_views.corporate_join, name='corporate_join'),
    path("corporate/join/<str:code>/confirm/", corporate_views.corporate_join_confirm, name='corporate_join_confirm'),
    path("share/<str:token>/", corporate_views.corporate_movie_share, name='corporate_movie_share'),
    path("my-subscription/", payment_views.my_subscription, name='my_subscription'),
    path("subscription/cancel/", payment_views.cancel_subscription_view, name='cancel_subscription'),
    path("subscription/", payment_views.subscription_plans, name='subscription_plans'),
    path("payment/checkout/", payment_views.checkout, name='payment_checkout'),
    path("payment/test/", payment_views.test_subscribe, name='test_subscribe'),
    path("payment/success/", payment_views.payment_success, name='payment_success'),
    path("payment/fail/", payment_views.payment_fail, name='payment_fail'),
    path("payment/click/", payment_views.click_callback, name='click_callback'),
    path("payment/payme/", payment_views.payme_callback, name='payme_callback'),
    path("stream/<int:movie_id>/<str:quality>/", stream_views.protected_stream, name='protected_stream'),
    path("stream/<int:movie_id>/trailer/", stream_views.public_trailer_stream, name='public_trailer'),
    path("telegram/webhook/", telegram_webhook.telegram_webhook, name='telegram_webhook'),

    path("content-api/", api_views.content_api_info, name='content_api_info'),
    path("api/v1/movies/", api_views.api_movies_list, name='api_movies_list'),
    path("api/v1/movies/<str:movie_uid>/", api_views.api_movie_detail, name='api_movie_detail'),
    path("api/v1/report-piracy/", api_views.api_report_piracy, name='api_report_piracy'),

    # SORTING 
    path("films/<str:sort_params>", views.movie_sorting, name="sort"),


    # login 
    path("login/", views.my_login, name='login'),
    path("logout/", views.logout_view, name='logout'),
    path("registration/", views.registration_view, name='register'),

    # RESET PASSWORD 

    path('reset_password/', auth_views.PasswordResetView.as_view(
        template_name = "registration/recover.html"), name ='reset_password'),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(
        template_name = "registration/password_reset_sent.html" ), name ='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name = "registration/password_reset_form.html"), name ='password_reset_confirm'),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name = "registration/password_reset_done.html"), name ='password_reset_complete'),

    # Admin Panel
    path('panel/', admin_views.dashboard, name='admin_dashboard'),
    path('panel/categories/', admin_views.category_list, name='admin_category_list'),
    path('panel/categories/add/', admin_views.category_add, name='admin_category_add'),
    path('panel/categories/<int:pk>/edit/', admin_views.category_edit, name='admin_category_edit'),
    path('panel/categories/<int:pk>/delete/', admin_views.category_delete, name='admin_category_delete'),
    path('panel/movies/', admin_views.movie_list, name='admin_movie_list'),
    path('panel/movies/add/', admin_views.movie_add, name='admin_movie_add'),
    path('panel/movies/<int:pk>/edit/', admin_views.movie_edit, name='admin_movie_edit'),
    path('panel/movies/<int:pk>/delete/', admin_views.movie_delete, name='admin_movie_delete'),
    path('panel/telegram-videos/', admin_views.telegram_video_list, name='admin_telegram_videos'),
    path('panel/telegram-videos/<int:pk>/link/', admin_views.telegram_video_link, name='admin_telegram_video_link'),
    path('panel/users/', admin_views.user_list, name='admin_user_list'),
    path('panel/watch-history/', admin_views.watch_history_list, name='admin_watch_history'),
    path('panel/subscriptions/', admin_views.subscription_list, name='admin_subscription_list'),
    path('panel/subscriptions/add/', admin_views.subscription_add, name='admin_subscription_add'),
    path('panel/subscriptions/<int:pk>/cancel/', admin_views.subscription_cancel, name='admin_subscription_cancel'),
    path('panel/plans/', admin_views.plan_list, name='admin_plan_list'),
    path('panel/plans/add/', admin_views.plan_add, name='admin_plan_add'),
    path('panel/plans/<int:pk>/edit/', admin_views.plan_edit, name='admin_plan_edit'),
    path('panel/plans/<int:pk>/delete/', admin_views.plan_delete, name='admin_plan_delete'),
    path('panel/corporate-requests/', admin_views.corporate_request_list, name='admin_corporate_requests'),
    path('panel/corporate-requests/<int:pk>/approve/', admin_views.corporate_request_approve, name='admin_corporate_approve'),
    path('panel/corporate-requests/<int:pk>/reject/', admin_views.corporate_request_reject, name='admin_corporate_reject'),
    path('panel/corporate/', admin_views.corporate_org_list, name='admin_corporate_orgs'),
    path('panel/corporate/<int:pk>/members/', admin_views.corporate_org_members, name='admin_corporate_org_members'),
    path('panel/payment-settings/', admin_views.payment_settings, name='admin_payment_settings'),
    path('panel/site-settings/', admin_views.site_settings, name='admin_site_settings'),
    path('panel/live/', admin_views.live_list, name='admin_live_list'),
    path('panel/live/add/', admin_views.live_add, name='admin_live_add'),
    path('panel/live/<int:pk>/edit/', admin_views.live_edit, name='admin_live_edit'),
    path('panel/live/<int:pk>/delete/', admin_views.live_delete, name='admin_live_delete'),
    path('panel/tickets/', admin_views.ticket_list, name='admin_ticket_list'),
    path('panel/tickets/add/', admin_views.ticket_add, name='admin_ticket_add'),
    path('panel/tickets/<int:pk>/edit/', admin_views.ticket_edit, name='admin_ticket_edit'),
    path('panel/tickets/<int:pk>/delete/', admin_views.ticket_delete, name='admin_ticket_delete'),
    path('panel/ticket-sales/', admin_views.ticket_sales, name='admin_ticket_sales'),
    path('panel/content-protection/', admin_views.content_protection, name='admin_content_protection'),
    path('panel/api-partners/', admin_views.api_partner_list, name='admin_api_partners'),
    path('panel/api-partners/add/', admin_views.api_partner_add, name='admin_api_partner_add'),
    path('panel/piracy-alerts/', admin_views.piracy_alert_list, name='admin_piracy_alerts'),
    path('panel/piracy-alerts/<int:pk>/resolve/', admin_views.piracy_alert_resolve, name='admin_piracy_resolve'),
]