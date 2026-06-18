from django.db import migrations, models


def set_uz_country_code(apps, schema_editor):
    TvChannel = apps.get_model('movie', 'TvChannel')
    TvChannel.objects.filter(country_code='').update(country_code='uz')
    TvChannel.objects.filter(country_code__isnull=True).update(country_code='uz')


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0037_tvchannel_logo_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='tvchannel',
            name='country_code',
            field=models.CharField(db_index=True, default='uz', max_length=2, verbose_name='Mamlakat'),
        ),
        migrations.RunPython(set_uz_country_code, migrations.RunPython.noop),
    ]
