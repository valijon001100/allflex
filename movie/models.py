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
    movie_uid = models.CharField('Yagona ID', max_length=20, unique=True, blank=True, null=True)
    digital_passport = models.TextField('Raqamli pasport (JSON)', blank=True, default='')
    digital_passport_code = models.CharField('Pasport kodi', max_length=64, blank=True, default='')
    watermark_token = models.CharField('Yashirin watermark', max_length=32, blank=True, default='')

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

    def ensure_protection_ids(self):
        from .protection_utils import (
            generate_digital_passport,
            generate_movie_uid,
            generate_watermark_token,
        )
        changed = []
        if not self.movie_uid:
            for _ in range(30):
                code = generate_movie_uid()
                if not Movie.objects.filter(movie_uid=code).exclude(pk=self.pk).exists():
                    self.movie_uid = code
                    changed.append('movie_uid')
                    break
        if not self.watermark_token:
            self.watermark_token = generate_watermark_token()
            changed.append('watermark_token')
        if not self.digital_passport or not self.digital_passport_code:
            passport_json, passport_code = generate_digital_passport(
                self.movie_uid or 'PENDING',
                self.title or 'Untitled',
                self.watermark_token or 'PENDING',
            )
            self.digital_passport = passport_json
            self.digital_passport_code = passport_code
            changed.extend(['digital_passport', 'digital_passport_code'])
        return changed

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new or not self.movie_uid or not self.watermark_token:
            changed = self.ensure_protection_ids()
            if changed:
                super().save(update_fields=changed)

    def get_streams_dict(self):
        streams = {}
        for s in self.video_streams.all():
            playback = s.get_playback_url()
            if playback:
                streams[s.quality] = playback
        if not streams and self.video_url:
            streams['720'] = self.video_url
        return streams

    def get_protected_streams_dict(self, user=None):
        from .stream_utils import sign_stream_path
        streams = {}
        for s in self.video_streams.all():
            if s.get_playback_url():
                path = reverse(
                    'movie:protected_stream',
                    kwargs={'movie_id': self.pk, 'quality': s.quality},
                )
                if user and user.is_authenticated:
                    path = sign_stream_path(path, self.pk, s.quality, user.pk)
                streams[s.quality] = path
        if not streams and self.video_url:
            path = reverse(
                'movie:protected_stream',
                kwargs={'movie_id': self.pk, 'quality': '720'},
            )
            if user and user.is_authenticated:
                path = sign_stream_path(path, self.pk, '720', user.pk)
            streams['720'] = path
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
    referral_code = models.CharField(max_length=32, unique=True, blank=True)
    referred_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='referrals',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['organization', 'user']]
        verbose_name = 'Korporativ a\'zo'
        verbose_name_plural = 'Korporativ a\'zolar'

    def __str__(self):
        return f'{self.user.username} — {self.organization.company_name}'

    @property
    def referrals_count(self):
        return self.referrals.count()

    def _generate_referral_code(self):
        for _ in range(20):
            code = uuid.uuid4().hex[:12]
            if not CorporateMember.objects.filter(referral_code=code).exists():
                return code
        return uuid.uuid4().hex

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()
        super().save(*args, **kwargs)

    def get_referral_path(self):
        return reverse('movie:corporate_join', kwargs={'code': self.referral_code})


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


class TicketCategory(models.Model):
  CATEGORY_KINO = 'kino'
  CATEGORY_TEATR = 'teatr'
  CATEGORY_SIRK = 'sirk'

  name = models.CharField(max_length=100)
  name_uz = models.CharField(max_length=100, blank=True, default='')
  name_en = models.CharField(max_length=100, blank=True, default='')
  slug = models.SlugField(max_length=50, unique=True)
  icon = models.CharField(max_length=8, default='🎫')
  order = models.PositiveIntegerField(default=0)
  is_active = models.BooleanField(default=True)

  class Meta:
    verbose_name = 'Bilet bo\'limi'
    verbose_name_plural = 'Bilet bo\'limlari'
    ordering = ['order', 'name']

  def get_translated_name(self, lang='ru'):
    if lang == 'uz' and self.name_uz:
      return self.name_uz
    if lang == 'en' and self.name_en:
      return self.name_en
    return self.name

  def get_absolute_url(self):
    return reverse('movie:ticket_category', kwargs={'slug': self.slug})

  def __str__(self):
    return self.name


class TicketEvent(models.Model):
  category = models.ForeignKey(
    TicketCategory, on_delete=models.CASCADE, related_name='events',
  )
  title = models.CharField(max_length=250)
  slug = models.SlugField(max_length=120, unique=True)
  subtitle = models.CharField(max_length=200, blank=True, default='')
  description = models.TextField(blank=True)
  venue = models.CharField(max_length=200)
  venue_address = models.CharField(max_length=300, blank=True, default='')
  city = models.CharField(max_length=100, default='Toshkent')
  event_date = models.DateTimeField()
  poster = models.ImageField(upload_to='ticket_posters/%Y/%m', blank=True, null=True)
  price = models.DecimalField(max_digits=10, decimal_places=2)
  age_limit = models.CharField(max_length=20, blank=True, default='6+')
  language = models.CharField(max_length=80, blank=True, default='')
  is_premiere = models.BooleanField('Premyera', default=True)
  quantity_total = models.PositiveIntegerField(default=100)
  quantity_sold = models.PositiveIntegerField(default=0)
  is_active = models.BooleanField(default=True)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    verbose_name = 'Tadbir'
    verbose_name_plural = 'Tadbirlar'
    ordering = ['event_date']

  @property
  def tickets_left(self):
    return max(0, self.quantity_total - self.quantity_sold)

  @property
  def is_sold_out(self):
    return self.tickets_left <= 0

  def get_absolute_url(self):
    return reverse('movie:ticket_detail', kwargs={'slug': self.slug})

  def get_map_query(self):
    if self.venue_address:
      return self.venue_address
    return f'{self.venue}, {self.city}'

  def __str__(self):
    return self.title


class PaymentOrder(models.Model):
    ORDER_SUBSCRIPTION = 'subscription'
    ORDER_TICKET = 'ticket'
    ORDER_TYPE_CHOICES = [
        (ORDER_SUBSCRIPTION, 'Subscription'),
        (ORDER_TICKET, 'Ticket'),
    ]

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
    order_type = models.CharField(
        max_length=20, choices=ORDER_TYPE_CHOICES, default=ORDER_SUBSCRIPTION,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_orders')
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT,
        related_name='orders', null=True, blank=True,
    )
    ticket_event = models.ForeignKey(
        TicketEvent, on_delete=models.PROTECT,
        related_name='orders', null=True, blank=True,
    )
    ticket_quantity = models.PositiveIntegerField(default=1)
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


class PurchasedTicket(models.Model):
  order = models.ForeignKey(
    PaymentOrder, on_delete=models.CASCADE, related_name='purchased_tickets',
  )
  user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchased_tickets')
  event = models.ForeignKey(TicketEvent, on_delete=models.PROTECT, related_name='sold_tickets')
  ticket_code = models.CharField(max_length=32, unique=True)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    verbose_name = 'Sotilgan bilet'
    verbose_name_plural = 'Sotilgan biletlar'
    ordering = ['-created_at']

  def __str__(self):
    return f'{self.ticket_code} — {self.event.title}'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, default='', verbose_name='Telefon')
    subscriber_code = models.CharField(max_length=10, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Foydalanuvchi profili'
        verbose_name_plural = 'Foydalanuvchi profillari'

    def ensure_subscriber_code(self):
        from .protection_utils import generate_subscriber_code
        if self.subscriber_code:
            return False
        for _ in range(30):
            code = generate_subscriber_code()
            if not UserProfile.objects.filter(subscriber_code=code).exclude(pk=self.pk).exists():
                self.subscriber_code = code
                return True
        return False

    def save(self, *args, **kwargs):
        self.ensure_subscriber_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username} — {self.subscriber_code}'


class WatchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watch_history')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='watch_history')
    subscriber_code = models.CharField(max_length=10, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    watched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tomosha tarixi'
        verbose_name_plural = 'Tomosha tarixi'
        ordering = ['-watched_at']
        indexes = [
            models.Index(fields=['-watched_at']),
            models.Index(fields=['user', 'movie']),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.movie.title}'


class APIPartner(models.Model):
    TYPE_TELEGRAM = 'telegram'
    TYPE_SITE = 'site'
    TYPE_PLATFORM = 'platform'
    TYPE_CHOICES = [
        (TYPE_TELEGRAM, 'Telegram kanal'),
        (TYPE_SITE, 'Sayt'),
        (TYPE_PLATFORM, 'Platforma'),
    ]

    name = models.CharField(max_length=200)
    partner_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SITE)
    contact_email = models.EmailField(blank=True, default='')
    website = models.URLField(blank=True, default='')
    api_key = models.CharField(max_length=64, unique=True, blank=True)
    revenue_share_percent = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    total_requests = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'API hamkor'
        verbose_name_plural = 'API hamkorlar'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.api_key:
            from .protection_utils import generate_api_key
            self.api_key = generate_api_key()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class APIAccessLog(models.Model):
    partner = models.ForeignKey(
        APIPartner, null=True, blank=True, on_delete=models.SET_NULL, related_name='access_logs',
    )
    endpoint = models.CharField(max_length=200)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default='')
    is_authorized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class PiracyAlert(models.Model):
    STATUS_NEW = 'new'
    STATUS_REVIEWED = 'reviewed'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Yangi'),
        (STATUS_REVIEWED, 'Ko\'rib chiqilgan'),
        (STATUS_RESOLVED, 'Hal qilingan'),
    ]

    movie = models.ForeignKey(
        Movie, null=True, blank=True, on_delete=models.SET_NULL, related_name='piracy_alerts',
    )
    detected_url = models.URLField(blank=True, default='')
    detected_domain = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    notified_rights_holder = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Piratlik ogohlantirishi'
        verbose_name_plural = 'Piratlik ogohlantirishlari'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.detected_domain or "Noma\'lum"} — {self.get_status_display()}'


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
