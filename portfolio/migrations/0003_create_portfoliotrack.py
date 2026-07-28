from django.db import migrations, models
import django.db.models.deletion


def create_default_tracks(apps, schema_editor):
    Profile = apps.get_model("portfolio", "Profile")
    PortfolioTrack = apps.get_model("portfolio", "PortfolioTrack")
    for profile in Profile.objects.all():
        PortfolioTrack.objects.create(
            profile=profile,
            name="Default",
            slug="default",
            is_default=True,
            order=0,
        )


def reverse_default_tracks(apps, schema_editor):
    PortfolioTrack = apps.get_model("portfolio", "PortfolioTrack")
    PortfolioTrack.objects.filter(slug="default", is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0002_proficiency_delete_profiency"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortfolioTrack",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=110)),
                ("is_default", models.BooleanField(default=False)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tracks", to="portfolio.profile")),
            ],
            options={
                "verbose_name_plural": "Portfolio Tracks",
                "ordering": ["order", "id"],
                "unique_together": {("profile", "slug")},
            },
        ),
        migrations.RunPython(create_default_tracks, reverse_default_tracks),
    ]
