

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0009_rename_detections__detecti_f4276b_idx_sc_annotati_detecti_d47dae_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='detection',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
