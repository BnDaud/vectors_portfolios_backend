from datetime import date

from django.db import migrations


def experience_years_from_start_date(apps, schema_editor):
    """Turn each track's existing 'experience since' date into the new
    years-as-of-this-year pair, so every portfolio shows the same number it
    did before and then rolls over on January 1."""
    About = apps.get_model("portfolio", "About")
    today = date.today()
    for about in About.objects.all():
        if about.experience_since:
            years = max(0, (today - about.experience_since).days // 365)
        else:
            years = 0
        about.experience_base_years = years
        about.experience_base_year = today.year
        about.save(update_fields=["experience_base_years", "experience_base_year"])


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0013_about_experience_base_year_and_more"),
    ]

    operations = [
        # Reverse is a no-op: experience_since is untouched, and the new
        # columns are dropped by reversing 0013.
        migrations.RunPython(experience_years_from_start_date, migrations.RunPython.noop),
    ]
