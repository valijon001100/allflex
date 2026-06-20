from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0041_site_premieres'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='genre',
            options={'ordering': ['name_uz', 'name'], 'verbose_name': 'Genre', 'verbose_name_plural': 'Genres'},
        ),
        migrations.AlterField(
            model_name='genre',
            name='name',
            field=models.CharField(max_length=100, verbose_name='Genre name (RU)'),
        ),
        migrations.AddField(
            model_name='genre',
            name='name_en',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Name (EN)'),
        ),
        migrations.AddField(
            model_name='genre',
            name='name_uz',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Nomi (UZ)'),
        ),
    ]
