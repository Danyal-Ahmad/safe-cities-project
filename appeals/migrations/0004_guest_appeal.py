from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('appeals', '0003_professional_table_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challanappeal',
            name='submitted_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='appeals_submitted', to=settings.AUTH_USER_MODEL,
                help_text='Null when submitted as guest via public search (CNIC matched).',
            ),
        ),
        migrations.AddField(
            model_name='challanappeal',
            name='guest_cnic',
            field=models.CharField(blank=True, default='', max_length=15),
        ),
        migrations.AddField(
            model_name='challanappeal',
            name='guest_name',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]
