from django.db import migrations, models


class Migration(migrations.Migration):
    """How many portfolios an account may have. Existing accounts (the site owner's) get no limit."""

    dependencies = [
        ("portfolio", "0022_project_sharing_drop_old_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="max_portfolios",
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="google_sub",
            field=models.CharField(blank=True, editable=False, max_length=255, null=True, unique=True),
        ),
    ]
