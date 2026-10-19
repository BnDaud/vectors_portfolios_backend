from django.db import migrations


def link_each_project_to_its_portfolio(apps, schema_editor):
    Portfolio = apps.get_model('portfolio', 'Portfolio')
    for project in Portfolio.objects.exclude(track=None):
        project.tracks.add(project.track_id)


def link_back(apps, schema_editor):
    """Rolling back: each project returns to the first portfolio that showed it."""
    Portfolio = apps.get_model('portfolio', 'Portfolio')
    for project in Portfolio.objects.all():
        first = project.tracks.order_by('id').first()
        if first is not None:
            project.track_id = first.id
            project.save(update_fields=['track'])


class Migration(migrations.Migration):
    """Step 2 of 3: every existing project keeps showing in the one portfolio it was added to."""

    dependencies = [
        ('portfolio', '0020_project_sharing_schema'),
    ]

    operations = [
        migrations.RunPython(link_each_project_to_its_portfolio, link_back),
    ]
