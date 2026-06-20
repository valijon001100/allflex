from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0040_telegram_bot_wizard_step'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('premiere_slides_count', models.PositiveSmallIntegerField(default=5, verbose_name='Premyera slaydlar soni')),
                ('premiere_rotate_seconds', models.PositiveSmallIntegerField(default=6, verbose_name='Aylanish vaqti (sekund)')),
                ('premiere_title', models.CharField(blank=True, default='Premyeralar', max_length=120)),
                ('premiere_title_uz', models.CharField(blank=True, default='Premyeralar', max_length=120)),
                ('premiere_title_en', models.CharField(blank=True, default='Premieres', max_length=120)),
                ('premiere_enabled', models.BooleanField(default=True, verbose_name="Bosh sahifada ko'rsatish")),
            ],
            options={
                'verbose_name': 'Sayt sozlamalari',
                'verbose_name_plural': 'Sayt sozlamalari',
            },
        ),
        migrations.CreateModel(
            name='HomePremiere',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('movie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='home_premiere_slots', to='movie.movie')),
            ],
            options={
                'verbose_name': 'Bosh sahifa premyerasi',
                'verbose_name_plural': 'Bosh sahifa premyeralari',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='homepremiere',
            constraint=models.UniqueConstraint(fields=('movie',), name='unique_home_premiere_movie'),
        ),
    ]
