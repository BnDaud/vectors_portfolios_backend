from django.db import migrations, models
import django.db.models.deletion


def backfill_about_track(apps, schema_editor):
    About = apps.get_model("portfolio", "About")
    for about in About.objects.all():
        about.track = about.about.tracks.get(is_default=True)
        about.save(update_fields=["track"])


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0003_create_portfoliotrack"),
    ]

    operations = [
        migrations.AddField(
            model_name="about",
            name="track",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="about_new",
                to="portfolio.portfoliotrack",
            ),
        ),
        migrations.RunPython(backfill_about_track, reverse_backfill),
    ]
