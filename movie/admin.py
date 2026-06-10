from django.contrib import admin
from .models import *
# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "order", "is_active", "id"]
    list_display_links = ["name"]
    list_filter = ["parent", "is_active"]
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Genre)
class GenresAdmin(admin.ModelAdmin):
    list_display = ["name", "id"]
    list_display_links = ["name"]
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ["name", "id"]
    list_display_links = ["name"]
    prepopulated_fields = {"slug": ("name",)}

class MovieStreamInline(admin.TabularInline):
    model = MovieStream
    extra = 4
    max_num = 4


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "likes", "rating"]
    list_display_links = ["title"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [MovieStreamInline]

admin.site.register(Comment)
admin.site.register(LikedMovieList)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_corporate', 'price', 'duration_days', 'max_seats', 'access_movies', 'access_live', 'order', 'is_active']
    list_filter = ['is_active', 'is_corporate', 'access_movies', 'access_live']


@admin.register(CorporateOrganization)
class CorporateOrganizationAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'plan', 'max_seats', 'end_date', 'is_active']
    list_filter = ['is_active', 'plan']


@admin.register(CorporateMember)
class CorporateMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'added_at']


@admin.register(CorporateSubscriptionRequest)
class CorporateSubscriptionRequestAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'plan', 'seats_requested', 'status', 'created_at']
    list_filter = ['status', 'plan']


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'start_date', 'end_date', 'is_active', 'payment_amount']
    list_filter = ['is_active', 'plan']


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'plan', 'provider', 'amount', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'provider']
    readonly_fields = ['order_id', 'created_at', 'paid_at']