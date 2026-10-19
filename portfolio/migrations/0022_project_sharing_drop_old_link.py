from django.db import migrations


class Migration(migrations.Migration):
    """Step 3 of 3: the old single-portfolio link is no longer needed."""

    dependencies = [
        ('portfolio', '0021_project_sharing_copy'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='portfolio',
            name='track',
        ),
    ]
