from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0004_about_track_nullable"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="about",
            name="about",
        ),
        migrations.AlterField(
            model_name="about",
            name="track",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="about",
                to="portfolio.portfoliotrack",
            ),
        ),
    ]
