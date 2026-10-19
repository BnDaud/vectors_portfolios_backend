from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Step 1 of 3 (projects shared across portfolios): make room for the many-to-many next to the old link."""

    dependencies = [
        ('portfolio', '0019_project_description'),
    ]

    operations = [
        # the old single-portfolio link steps aside (nullable, new reverse name) so "items" can move to the new field
        migrations.AlterField(
            model_name='portfolio',
            name='track',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='old_items', to='portfolio.portfoliotrack'),
        ),
        migrations.AddField(
            model_name='portfolio',
            name='tracks',
            field=models.ManyToManyField(related_name='items', to='portfolio.portfoliotrack'),
        ),
    ]
