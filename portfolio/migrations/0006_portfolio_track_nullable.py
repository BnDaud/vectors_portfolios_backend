from django.db import migrations, models
import django.db.models.deletion


def backfill_portfolio_track(apps, schema_editor):
    Portfolio = apps.get_model("portfolio", "Portfolio")
    for item in Portfolio.objects.all():
        item.track = item.portfolio.tracks.get(is_default=True)
        item.save(update_fields=["track"])


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0005_finalize_about_track"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfolio",
            name="track",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items_new",
                to="portfolio.portfoliotrack",
            ),
        ),
        migrations.RunPython(backfill_portfolio_track, reverse_backfill),
    ]
