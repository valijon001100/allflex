from django.db import migrations, models


def rename_teleperedachi_category(apps, schema_editor):
    Category = apps.get_model('movie', 'Category')
    Category.objects.filter(slug='teleperedachi').update(
        name='Телеканалы',
        name_uz='Telekanallar',
        name_en='TV Channels',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0034_corporate_movie_share'),
    ]

    operations = [
        migrations.CreateModel(
            name='TvChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Kanal nomi')),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('tvg_id', models.CharField(blank=True, default='', max_length=120, verbose_name='TVG ID')),
                ('stream_url', models.URLField(verbose_name='Stream URL')),
                ('quality', models.CharField(blank=True, default='', max_length=40)),
                ('is_active', models.BooleanField(default=True, verbose_name='Faol')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Tartib')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Telekanal',
                'verbose_name_plural': 'Telekanallar',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.RunPython(rename_teleperedachi_category, migrations.RunPython.noop),
    ]
