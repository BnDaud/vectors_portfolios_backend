from django.db import migrations

CONTACT_FIELDS = [
    "display_pic", "github", "linkedin", "whatapp", "facebook",
    "twitter", "email", "phone_number",
]


def copy_profile_contact_to_tracks(apps, schema_editor):
    """Give every existing track its own copy of its owner's dp/contact values,
    so each portfolio looks exactly as before and can diverge from now on."""
    PortfolioTrack = apps.get_model("portfolio", "PortfolioTrack")
    for track in PortfolioTrack.objects.select_related("profile"):
        for field in CONTACT_FIELDS:
            setattr(track, field, getattr(track.profile, field))
        track.save(update_fields=CONTACT_FIELDS)


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0011_portfoliotrack_contact_fields"),
    ]

    operations = [
        # Reverse is a no-op: the Profile columns are untouched, and the
        # track columns are dropped by reversing 0011.
        migrations.RunPython(copy_profile_contact_to_tracks, migrations.RunPython.noop),
    ]
