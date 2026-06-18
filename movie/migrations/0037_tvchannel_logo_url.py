from django.db import migrations, models


def backfill_logos(apps, schema_editor):
    TvChannel = apps.get_model('movie', 'TvChannel')
    try:
        from movie.iptv_logos import refresh_channel_logos
        refresh_channel_logos(TvChannel.objects.all())
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0036_load_tv_channels'),
    ]

    operations = [
        migrations.AddField(
            model_name='tvchannel',
            name='logo_url',
            field=models.URLField(blank=True, default='', verbose_name='Logo URL'),
        ),
        migrations.RunPython(backfill_logos, migrations.RunPython.noop),
    ]
