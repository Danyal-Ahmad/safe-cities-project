from django.db import migrations, models


def rename_flagged_status(apps, schema_editor):
    Detection = apps.get_model('detections', 'Detection')
    Detection.objects.filter(status='flagged_for_dig').update(status='flagged_officer')


def revert_flagged_status(apps, schema_editor):
    Detection = apps.get_model('detections', 'Detection')
    Detection.objects.filter(status='flagged_officer').update(status='flagged_for_dig')


class Migration(migrations.Migration):

    dependencies = [
        ('detections', '0011_remove_annotation_created_by_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_flagged_status, revert_flagged_status),
        migrations.AlterField(
            model_name='detection',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_review', 'Pending Review'),
                    ('confirmed', 'Confirmed'),
                    ('rejected', 'Rejected (False Positive)'),
                    ('flagged_officer', 'Flagged for Officer Review'),
                ],
                default='pending_review',
                max_length=20,
            ),
        ),
    ]
