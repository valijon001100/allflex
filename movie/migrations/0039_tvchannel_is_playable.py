from django.db import migrations, models


def mark_cinerama_unplayable(apps, schema_editor):
    TvChannel = apps.get_model('movie', 'TvChannel')
    TvChannel.objects.filter(stream_url__icontains='cinerama.uz').update(is_playable=False)


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0038_tvchannel_country_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='tvchannel',
            name='is_playable',
            field=models.BooleanField(db_index=True, default=True, verbose_name='Ishlaydi'),
        ),
        migrations.RunPython(mark_cinerama_unplayable, migrations.RunPython.noop),
    ]
