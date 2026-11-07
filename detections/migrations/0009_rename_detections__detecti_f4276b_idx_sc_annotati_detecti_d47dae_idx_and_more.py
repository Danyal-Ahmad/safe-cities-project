

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0008_detection_vehicle_plate_images'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='annotation',
            new_name='sc_annotati_detecti_d47dae_idx',
            old_name='detections__detecti_f4276b_idx',
        ),
        migrations.RenameIndex(
            model_name='annotation',
            new_name='sc_annotati_type_3907f5_idx',
            old_name='detections__type_c88fbf_idx',
        ),
        migrations.RenameIndex(
            model_name='annotation',
            new_name='sc_annotati_object__126f68_idx',
            old_name='detections__object__88d049_idx',
        ),
        migrations.RenameIndex(
            model_name='detection',
            new_name='sc_detectio_status_f459c3_idx',
            old_name='detections__status_672746_idx',
        ),
        migrations.RenameIndex(
            model_name='detection',
            new_name='sc_detectio_camera__810d86_idx',
            old_name='detections__camera__d19011_idx',
        ),
        migrations.RenameIndex(
            model_name='detection',
            new_name='sc_detectio_reviewe_b5eae7_idx',
            old_name='detections__reviewe_31d6ab_idx',
        ),
    ]
