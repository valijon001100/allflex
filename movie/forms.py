from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from transliterate import translit
from .models import (
    Category, Comment, CorporateMember, CorporateOrganization,
    CorporateSubscriptionRequest, LiveStream, Movie, MovieStream,
    SubscriptionPlan, UserSubscription,
)

STREAM_QUALITIES = ['480', '720', '1080', '4k']
STREAM_LABELS = {'480': '480p', '720': '720p', '1080': '1080p', '4k': '4K'}


def _apply_labels(form, labels):
    for name, label in labels.items():
        if name in form.fields:
            form.fields[name].label = label


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_('Электронная почта'))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-control auth-input",
                "placeholder": "Имя пользователя",
                "maxlength": "25",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control auth-input",
                "placeholder": "Электронная почта",
                "maxlength": "40",
            }),
            "password1": forms.PasswordInput(attrs={
                "class": "form-control auth-input",
                "placeholder": "Пароль",
            }),
            "password2": forms.PasswordInput(attrs={
                "class": "form-control auth-input",
                "placeholder": "Подтвердите пароль",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control auth-input')
        self.fields['password1'].help_text = _('Kamida 6 ta belgi')
        self.fields['password2'].label = _('Подтвердите пароль')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_('Bu email allaqachon ro\'yxatdan o\'tgan'))
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(_('Bu foydalanuvchi nomi band'))
        return username


class MovieForm(forms.ModelForm):
    stream_480 = forms.FileField(required=False, label=_('Видео 480p'), widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/*,.mp4,.webm,.mkv,.m3u8'}))
    stream_720 = forms.FileField(required=False, label=_('Видео 720p'), widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/*,.mp4,.webm,.mkv,.m3u8'}))
    stream_1080 = forms.FileField(required=False, label=_('Видео 1080p'), widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/*,.mp4,.webm,.mkv,.m3u8'}))
    stream_4k = forms.FileField(required=False, label=_('Видео 4K'), widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/*,.mp4,.webm,.mkv,.m3u8'}))

    class Meta:
        model = Movie
        fields = [
            'title', 'title_uz', 'title_en', 'slug', 'category', 'poster', 'description', 'short_description',
            'genres', 'actors', 'quality', 'duration', 'year', 'country',
            'is_premium', 'rating',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'title_uz': forms.TextInput(attrs={'class': 'form-control'}),
            'title_en': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'short_description': forms.TextInput(attrs={'class': 'form-control'}),
            'genres': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'actors': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'quality': forms.TextInput(attrs={'class': 'form-control'}),
            'duration': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        title = self.cleaned_data.get('title', '')
        if not slug and title:
            try:
                slug = slugify(translit(title, 'ru', reversed=True))
            except Exception:
                slug = slugify(title)
        if not slug:
            raise forms.ValidationError(_('Slug yaratib bo\'lmadi. Qo\'lda kiriting.'))
        qs = Movie.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_('Bu slug allaqachon mavjud.'))
        return slug

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_labels(self, {
            'title': _('Название (RU)'),
            'title_uz': _('Название (UZ)'),
            'title_en': _('Название (EN)'),
            'slug': _('Slug (URL)'),
            'category': _('Раздел'),
            'poster': _('Постер'),
            'description': _('Описание'),
            'short_description': _('Краткое описание'),
            'genres': _('Жанры'),
            'actors': _('Актёры'),
            'quality': _('Качество'),
            'duration': _('Длительность'),
            'year': _('Год'),
            'country': _('Страна'),
            'is_premium': _('Premium'),
            'rating': _('Рейтинг'),
        })
        def _category_label(cat):
            return f"└ {cat.name}" if cat.parent_id else cat.name

        self.fields['category'].queryset = Category.objects.select_related('parent').order_by(
            'parent__order', 'parent__name', 'order', 'name'
        )
        self.fields['category'].label_from_instance = _category_label

        if self.instance.pk:
            for q in STREAM_QUALITIES:
                stream = self.instance.video_streams.filter(quality=q).first()
                if stream and stream.video_file:
                    self.fields[f'stream_{q}'].help_text = _('Joriy fayl: %(file)s') % {'file': stream.video_file.name}

    def save(self, commit=True):
        movie = super().save(commit=commit)
        if commit:
            for q in STREAM_QUALITIES:
                uploaded = self.cleaned_data.get(f'stream_{q}')
                if uploaded:
                    stream, _ = MovieStream.objects.get_or_create(movie=movie, quality=q)
                    stream.video_file = uploaded
                    stream.url = ''
                    stream.save()
        return movie


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['parent', 'name', 'name_uz', 'name_en', 'slug', 'is_active', 'order']
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фильмы'}),
            'name_uz': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filmlar'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Movies'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'filmy'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.fixed_parent = kwargs.pop('fixed_parent', None)
        super().__init__(*args, **kwargs)
        _apply_labels(self, {
            'parent': _('Asosiy bo\'lim'),
            'name': _('Название (RU)'),
            'name_uz': _('Название (UZ)'),
            'name_en': _('Название (EN)'),
            'slug': _('Slug (URL)'),
            'is_active': _('Показать в меню'),
            'order': _('Порядок'),
        })
        parent_qs = Category.objects.filter(parent__isnull=True).order_by('order', 'name')
        if self.instance.pk:
            parent_qs = parent_qs.exclude(pk=self.instance.pk)
        self.fields['parent'].queryset = parent_qs
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = _('— Asosiy bo\'lim (yuqori daraja) —')

        if self.fixed_parent:
            self.fields['parent'].initial = self.fixed_parent.pk
            self.fields['parent'].widget = forms.HiddenInput()
        elif self.instance.pk and self.instance.children.exists():
            self.fields['parent'].disabled = True

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        if self.fixed_parent:
            return self.fixed_parent
        if parent and parent.parent_id:
            raise forms.ValidationError(_('Ichki bo\'lim faqat asosiy bo\'lim ichida bo\'lishi mumkin.'))
        if self.instance.pk and parent and parent.pk == self.instance.pk:
            raise forms.ValidationError(_('Bo\'lim o\'zining ichki bo\'limi bo\'la olmaydi.'))
        if self.instance.pk and self.instance.children.exists() and parent:
            raise forms.ValidationError(_('Ichki bo\'limlari bor bo\'limni boshqa bo\'lim ichiga qo\'yib bo\'lmaydi.'))
        return parent


class LiveStreamForm(forms.ModelForm):
    class Meta:
        model = LiveStream
        fields = ['title', 'slug', 'description', 'poster', 'stream_url', 'is_live', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'poster': forms.FileInput(attrs={'class': 'form-control'}),
            'stream_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://.../live.m3u8'}),
            'is_live': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_labels(self, {
            'title': _('Название'),
            'slug': _('Slug (URL)'),
            'description': _('Описание'),
            'poster': _('Постер'),
            'stream_url': _('URL прямого эфира'),
            'is_live': _('Сейчас в эфире'),
            'is_active': _('Активен'),
        })


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = UserSubscription
        fields = ['user', 'plan', 'end_date', 'payment_amount', 'is_active']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'plan': forms.Select(attrs={'class': 'form-control'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'payment_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_labels(self, {
            'user': _('Пользователь'),
            'plan': _('Тариф'),
            'end_date': _('Дата окончания'),
            'payment_amount': _('Сумма оплаты'),
            'is_active': _('Активна'),
        })


class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name', 'price', 'duration_days', 'description',
            'access_movies', 'access_live', 'is_corporate', 'max_seats',
            'order', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Standart'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Tarif haqida qisqa ma\'lumot...',
            }),
            'access_movies': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'access_live': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_corporate': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_labels(self, {
            'name': _('Название тарифа'),
            'price': _('Цена (сум)'),
            'duration_days': _('Muddat (kun)'),
            'description': _('Описание'),
            'access_movies': _('Доступ к фильмам'),
            'access_live': _('Доступ к прямому эфиру'),
            'is_corporate': _('Korporativ tarif'),
            'max_seats': _('Xodimlar soni'),
            'order': _('Tartib'),
            'is_active': _('Активен'),
        })

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('access_movies') and not cleaned.get('access_live'):
            raise forms.ValidationError(_('Kamida bitta kirish huquqi tanlanishi kerak.'))
        if cleaned.get('is_corporate') and cleaned.get('max_seats', 0) < 1:
            raise forms.ValidationError(_('Korporativ tarif uchun xodimlar soni kamida 1 bo\'lishi kerak.'))
        return cleaned


class CorporateRequestForm(forms.ModelForm):
    class Meta:
        model = CorporateSubscriptionRequest
        fields = ['company_name', 'contact_name', 'email', 'phone', 'seats_requested', 'message']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'OOO Kompaniya'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+998...'}),
            'seats_requested': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan
        _apply_labels(self, {
            'company_name': _('Kompaniya nomi'),
            'contact_name': _('Mas\'ul shaxs'),
            'email': _('Email'),
            'phone': _('Telefon'),
            'seats_requested': _('Xodimlar soni'),
            'message': _('Qo\'shimcha ma\'lumot'),
        })

    def clean_seats_requested(self):
        seats = self.cleaned_data['seats_requested']
        if self.plan and seats > self.plan.max_seats:
            raise forms.ValidationError(
                _('Maksimal %s ta xodim uchun so\'rov yuborish mumkin.') % self.plan.max_seats
            )
        return seats


class CorporateMemberForm(forms.Form):
    username = forms.CharField(
        label=_('Foydalanuvchi nomi'),
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_username(self):
        from django.contrib.auth.models import User
        username = self.cleaned_data['username'].strip()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError(_('Foydalanuvchi topilmadi.'))
        if self.organization and CorporateMember.objects.filter(
            organization=self.organization, user=user,
        ).exists():
            raise forms.ValidationError(_('Bu foydalanuvchi allaqachon qo\'shilgan.'))
        self.cleaned_data['user'] = user
        return username


class PaymentSettingsForm(forms.ModelForm):
    class Meta:
        from .models import PaymentSettings
        model = PaymentSettings
        fields = [
            'click_merchant_id', 'click_service_id', 'click_secret_key',
            'payme_merchant_id', 'payme_secret_key', 'test_mode_enabled',
        ]
        widgets = {
            'click_merchant_id': forms.TextInput(attrs={'class': 'form-control'}),
            'click_service_id': forms.TextInput(attrs={'class': 'form-control'}),
            'click_secret_key': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'payme_merchant_id': forms.TextInput(attrs={'class': 'form-control'}),
            'payme_secret_key': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'test_mode_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_labels(self, {
            'click_merchant_id': _('Click Merchant ID'),
            'click_service_id': _('Click Service ID'),
            'click_secret_key': _('Click Secret Key'),
            'payme_merchant_id': _('Payme Merchant ID'),
            'payme_secret_key': _('Payme Secret Key'),
            'test_mode_enabled': _('Sinov rejimi (DEBUG)'),
        })


class CommentForm(forms.ModelForm):

    class Meta:
        model = Comment
        # fields = ("name", "comment")
        fields = "__all__"
        exclude = ["movie"]
        
        widgets = {
            "name":forms.TextInput(attrs={"class":"form-control"}),
            "comment":forms.Textarea(attrs={"class":"form-control", "rows":3}),
        }