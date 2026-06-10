import uuid

from django.urls import reverse
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.
class Category(models.Model):
    """Model definition for Category."""
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name='Asosiy bo\'lim',
    )
    name = models.CharField("Category name (RU)", max_length=100)
    name_uz = models.CharField("Nomi (UZ)", max_length=100, blank=True, default='')
    name_en = models.CharField("Name (EN)", max_length=100, blank=True, default='')
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField("Navbar da ko'rsatish", default=True)
    order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def get_absolute_url(self):
        return reverse('movie:category_list', kwargs={'slug': self.slug})

    def get_translated_name(self, lang='ru'):
        if lang == 'uz' and self.name_uz:
            return self.name_uz
        if lang == 'en' and self.name_en:
            return self.name_en
        return self.name

    @property
    def is_parent(self):
        return self.parent_id is None

    def __str__(self):
        if self.parent_id:
            return f"{self.parent.name} → {self.name}"
        return f"{self.name}"

class Genre(models.Model):
    """Model definition for Genre."""
    name = models.CharField("Genre name", max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    # TODO: Define fields here

    class Meta:
        """Meta definition for Genre."""

        verbose_name = 'Genre'
        verbose_name_plural = 'Genres'

    def __str__(self):
        """Unicode representation of Genre."""
        return f"{self.name}"

class Actor(models.Model):
    """Model definition for Actor."""
    name = models.CharField("Actor name", max_length=150)
    slug = models.SlugField(max_length=100, unique=True)
    age = models.PositiveIntegerField("Actor age",default=0)
    image = models.ImageField("Actor image", upload_to='actor_images/')
    # TODO: Define fields here

    class Meta:
        """Meta definition for Actor."""

        verbose_name = 'Actor'
        verbose_name_plural = 'Actors'

    def __str__(self):
        """Unicode representation of Actor."""
        return f"{self.name}"

class Movie(models.Model):
    """Model definition for Movie."""
    actors = models.ManyToManyField(Actor)
    genres = models.ManyToManyField(Genre)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='movie_category')
    poster = models.ImageField(upload_to='movie_posters/%Y/%m')
    title = models.CharField("Movie title (RU)", max_length=250)
    title_uz = models.CharField("Nomi (UZ)", max_length=250, blank=True, default='')
    title_en = models.CharField("Title (EN)", max_length=250, blank=True, default='')
    slug = models.SlugField(max_length=100, unique=True)
    description =models.TextField()
    short_description = models.CharField("Short title", max_length=550, blank=True)
    likes = models.PositiveIntegerField(default=0)
    dislikes = models.PositiveIntegerField(default=0)
    rating = models.FloatField(default=0)
    quality = models.CharField("Quality", max_length=50, blank=True)
    duration = models.CharField("Duration", max_length=50, blank=True)
    year = models.CharField(max_length=5, default="2026")
    country = models.CharField(max_length=50, default="USA")
    video_url = models.URLField("Video URL", blank=True, default="")
    is_premium = models.BooleanField("Premium only", default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        """Meta definition for Movie."""

        verbose_name = 'Movie'
        verbose_name_plural = 'Movies'

    def get_translated_title(self, lang=None):
        from django.utils.translation import get_language
        lang = lang or get_language() or 'ru'
        if lang == 'uz':
            return self.title_uz or self.title
        if lang == 'en':
            return self.title_en or self.title
        return self.title

    def __str__(self):
        """Unicode representation of Movie."""
        return f"{self.title}"

    def get_streams_dict(self):
        streams = {}
        for s in self.video_streams.all():
            playback = s.get_playback_url()
            if playback:
                streams[s.quality] = playback
        if not streams and self.video_url:
            streams['720'] = self.video_url
        return streams

    def get_protected_streams_dict(self):
        streams = {}
        for s in self.video_streams.all():
            if s.get_playback_url():
                streams[s.quality] = reverse(
                    'movie:protected_stream',
                    kwargs={'movie_id': self.pk, 'quality': s.quality},
                )
        if not streams and self.video_url:
            streams['720'] = reverse(
                'movie:protected_stream',
                kwargs={'movie_id': self.pk, 'quality': '720'},
            )
        return streams


class MovieStream(models.Model):
    QUALITY_CHOICES = [
        ('480', '480p'),
        ('720', '720p'),
        ('1080', '1080p'),
        ('4k', '4K'),
    ]
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='video_streams')
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES)
    video_file = models.FileField(upload_to='movies/videos/%Y/%m/', blank=True, null=True)
    url = models.URLField(blank=True, default='')

    class Meta:
        unique_together = [['movie', 'quality']]
        ordering = ['quality']

    def get_playback_url(self):
        if self.video_file:
            return self.video_file.url
        return self.url or ''

    def __str__(self):
        return f"{self.movie.title} — {self.get_quality_display()}"


class Comment(models.Model):
    """Model definition for Comment."""
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT,
    related_name="movie_comments", null=True)
    name = models.CharField("Name", max_length=50, blank=True, default="Гость")
    comment = models.TextField()
    # TODO: Define fields here

    class Meta:
        """Meta definition for Comment."""

        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        ordering = ["-id"]

    def __str__(self):
        """Unicode representation of Comment."""
        return f"{self.name}"




class LikedMovieList(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_like_list')
    movie = models.ManyToManyField(Movie, blank=True)

    def __str__(self):
        return f"{self.user.username}"


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    description = models.TextField(blank=True)
    access_movies = models.BooleanField('Kinolar', default=True)
    access_live = models.BooleanField('Jonli efir', default=True)
    is_corporate = models.BooleanField('Korporativ tarif', default=False)
    max_seats = models.PositiveIntegerField(
        'Xodimlar soni (korporativ)',
        default=10,
        help_text='Korporativ tarif uchun maksimal foydalanuvchilar soni',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['-is_corporate', 'order', 'price']

    def __str__(self):
        return f"{self.name} — {self.price}"

    def get_access_list(self):
        from django.utils.translation import gettext as _
        items = []
        if self.access_movies:
            items.append(_('Kinolar'))
        if self.access_live:
            items.append(_('Jonli efir'))
        return items

    def get_access_display(self):
        items = self.get_access_list()
        return ', '.join(str(i) for i in items) if items else '—'


class CorporateOrganization(models.Model):
    company_name = models.CharField(max_length=200)
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='corporate_orgs',
        limit_choices_to={'is_corporate': True},
    )
    contact_name = models.CharField(max_length=150, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=30, blank=True, default='')
    admin_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_corporate_orgs',
    )
    max_seats = models.PositiveIntegerField(default=10)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Korporativ tashkilot'
        verbose_name_plural = 'Korporativ tashkilotlar'
        ordering = ['-created_at']

    def __str__(self):
        return self.company_name

    @property
    def is_valid(self):
        return self.is_active and self.end_date > timezone.now()

    @property
    def seats_used(self):
        return self.members.count()

    @property
    def seats_available(self):
        return max(0, self.max_seats - self.seats_used)


class CorporateMember(models.Model):
    organization = models.ForeignKey(
        CorporateOrganization,
        on_delete=models.CASCADE,
        related_name='members',
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='corporate_memberships')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['organization', 'user']]
        verbose_name = 'Korporativ a\'zo'
        verbose_name_plural = 'Korporativ a\'zolar'

    def __str__(self):
        return f'{self.user.username} — {self.organization.company_name}'


class CorporateSubscriptionRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Kutilmoqda'),
        (STATUS_APPROVED, 'Tasdiqlangan'),
        (STATUS_REJECTED, 'Rad etilgan'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='corporate_requests',
        null=True,
        blank=True,
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='corporate_requests',
        limit_choices_to={'is_corporate': True},
    )
    company_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    seats_requested = models.PositiveIntegerField(default=10)
    message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Korporativ so\'rov'
        verbose_name_plural = 'Korporativ so\'rovlar'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company_name} — {self.get_status_display()}'


class UserSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscribers')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.user.username} — {self.plan.name}"

    @property
    def is_valid(self):
        return self.is_active and self.end_date > timezone.now()


class PaymentSettings(models.Model):
    click_merchant_id = models.CharField(max_length=64, blank=True, default='')
    click_service_id = models.CharField(max_length=64, blank=True, default='')
    click_secret_key = models.CharField(max_length=128, blank=True, default='')
    payme_merchant_id = models.CharField(max_length=64, blank=True, default='')
    payme_secret_key = models.CharField(max_length=128, blank=True, default='')
    test_mode_enabled = models.BooleanField('Sinov rejimi (DEBUG)', default=True)

    class Meta:
        verbose_name = 'To\'lov sozlamalari'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'To\'lov sozlamalari'


class PaymentOrder(models.Model):
    PROVIDER_CLICK = 'click'
    PROVIDER_PAYME = 'payme'
    PROVIDER_TEST = 'test'
    PROVIDER_CHOICES = [
        (PROVIDER_CLICK, 'Click'),
        (PROVIDER_PAYME, 'Payme'),
        (PROVIDER_TEST, 'Test'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_ERROR, 'Error'),
    ]

    order_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_orders')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='orders')
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    external_id = models.CharField(max_length=255, blank=True, default='')
    prepare_id = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_id} — {self.user.username} — {self.status}'

    @property
    def amount_tiyin(self):
        return int(self.amount * 100)


class LiveStream(models.Model):
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    poster = models.ImageField(upload_to='live_posters/%Y/%m', blank=True, null=True)
    stream_url = models.URLField('Jonli efir URL', blank=True, default='')
    is_live = models.BooleanField('Hozir efirda', default=False)
    is_active = models.BooleanField('Faol', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Live Stream'
        verbose_name_plural = 'Live Streams'
        ordering = ['-is_live', '-created_at']

    def __str__(self):
        return self.title

    def get_playback_url(self):
        return self.stream_url or ''
