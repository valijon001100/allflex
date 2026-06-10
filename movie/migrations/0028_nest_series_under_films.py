from django.db import migrations


def nest_under_films(apps, schema_editor):
    Category = apps.get_model('movie', 'Category')
    filmy = Category.objects.filter(slug='filmy', parent__isnull=True).first()
    if not filmy:
        return
    for slug in ('serialy', 'skoro-na-sajte'):
        Category.objects.filter(slug=slug, parent__isnull=True).update(parent=filmy)


def unnest(apps, schema_editor):
    Category = apps.get_model('movie', 'Category')
    for slug in ('serialy', 'skoro-na-sajte'):
        Category.objects.filter(slug=slug).update(parent=None)


class Migration(migrations.Migration):

    dependencies = [
        ('movie', '0027_content_protection'),
    ]

    operations = [
        migrations.RunPython(nest_under_films, unnest),
    ]
