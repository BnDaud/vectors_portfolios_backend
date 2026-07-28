from datetime import date, timedelta

from django.db import migrations, models


def backfill_experience_since(apps, schema_editor):
    About = apps.get_model("portfolio", "About")
    for about in About.objects.all():
        years = about.years_of_experience or 0
        about.experience_since = date.today() - timedelta(days=365 * years)
        about.save(update_fields=["experience_since"])


def reverse_backfill(apps, schema_editor):
    About = apps.get_model("portfolio", "About")
    for about in About.objects.all():
        if about.experience_since:
            years = max(0, (date.today() - about.experience_since).days // 365)
        else:
            years = 0
        about.years_of_experience = years
        about.save(update_fields=["years_of_experience"])


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0007_finalize_portfolio_track_and_goal"),
    ]

    operations = [
        migrations.AddField(
            model_name="about",
            name="experience_since",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.RunPython(backfill_experience_since, reverse_backfill),
        migrations.RemoveField(
            model_name="about",
            name="years_of_experience",
        ),
    ]
