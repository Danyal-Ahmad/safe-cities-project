from django.db import migrations, models


def normalize_status(apps, schema_editor):
    ChallanAppeal = apps.get_model('appeals', 'ChallanAppeal')
    ChallanAppeal.objects.filter(status='escalated').update(status='pending')


class Migration(migrations.Migration):
    dependencies = [
        ('appeals', '0006_challanappeal_updated_at'),
    ]

    operations = [
        migrations.RunPython(normalize_status, migrations.RunPython.noop),
        migrations.RemoveField(model_name='challanappeal', name='current_stage'),
        migrations.RemoveField(model_name='challanappeal', name='is_escalated'),
        migrations.RemoveField(model_name='challanappeal', name='escalated_at'),
        migrations.RemoveField(model_name='challanappeal', name='escalation_reason'),
        migrations.RemoveField(model_name='challanappeal', name='dig_comment'),
        migrations.RemoveField(model_name='challanappeal', name='dig_reviewed_by'),
        migrations.RemoveField(model_name='challanappeal', name='dig_reviewed_at'),
        migrations.RemoveField(model_name='challanappeal', name='officer_comment'),
        migrations.AlterField(
            model_name='challanappeal',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10),
        ),
    ]
