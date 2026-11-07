from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
class Migration(migrations.Migration):

    dependencies = [
        ('appeals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='challanappeal',
            name='current_stage',
            field=models.CharField(
                max_length=10,
                choices=[('officer', 'Officer Review'), ('ssp', 'SSP Review'), ('dig', 'DIG Review')],
                default='officer',
            ),
        ),
        migrations.AddField(
            model_name='challanappeal',
            name='ssp_comment',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='challanappeal',
            name='ssp_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='challanappeal',
            name='ssp_reviewed_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='appeals_ssp_reviewed',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
