from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0006_portfolio_track_nullable"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="portfolio",
            name="portfolio",
        ),
        migrations.AlterField(
            model_name="portfolio",
            name="track",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="portfolio.portfoliotrack",
            ),
        ),
        migrations.AddField(
            model_name="resume",
            name="certificate_link",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="school",
            name="certificate_link",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="proficiency",
            name="certificate_link",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.CreateModel(
            name="Goal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True, default="")),
                ("target_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("in_progress", "In Progress"), ("completed", "Completed")], default="in_progress", max_length=20)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="goals", to="portfolio.profile")),
            ],
        ),
    ]
