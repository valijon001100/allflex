from django.db import migrations, models

CATEGORY_DATA = {
    'filmy': {'uz': 'Filmlar', 'en': 'Movies', 'order': 1},
    'serialy': {'uz': 'Seriallar', 'en': 'TV Series', 'order': 2},
    'teleperedachi': {'uz': "Teleko'rsatuvlar", 'en': 'TV Shows', 'order': 3},
    'multfilmy': {'uz': 'Multfilmlar', 'en': 'Cartoons', 'order': 4},
    'skoro-na-sajte': {'uz': 'Tez kunda', 'en': 'Coming Soon', 'order': 5},
    'podborki': {'uz': "To'plamlar", 'en': 'Collections', 'order': 6},
}


def populate_category_names(apps, schema_editor):
    Category = apps.get_model('movie', 'Category')
    for cat in Category.objects.all():
        data = CATEGORY_DATA.get(cat.slug, {})
        cat.name_uz = data.get('uz', '')
        cat.name_en = data.get('en', '')
        cat.order = data.get('order', 0)
        cat.is_active = True
        cat.save()


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0016_livestream'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='name_en',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Name (EN)'),
        ),
        migrations.AddField(
            model_name='category',
            name='name_uz',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Nomi (UZ)'),
        ),
        migrations.AddField(
            model_name='category',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name="Navbar da ko'rsatish"),
        ),
        migrations.AddField(
            model_name='category',
            name='order',
            field=models.PositiveIntegerField(default=0, verbose_name='Tartib'),
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['order', 'name'], 'verbose_name': 'Category', 'verbose_name_plural': 'Categories'},
        ),
        migrations.RunPython(populate_category_names, migrations.RunPython.noop),
    ]
