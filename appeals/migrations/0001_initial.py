from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('challans', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChallanAppeal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('evidence_file', models.ImageField(blank=True, null=True, upload_to='appeals/evidence/%Y/%m/%d/')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('escalated', 'Escalated to DIG')], default='pending', max_length=10)),
                ('officer_comment', models.TextField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('is_escalated', models.BooleanField(default=False)),
                ('escalated_at', models.DateTimeField(blank=True, null=True)),
                ('escalation_reason', models.TextField(blank=True, null=True)),
                ('dig_comment', models.TextField(blank=True, null=True)),
                ('dig_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('challan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appeals', to='challans.challan')),
                ('dig_reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appeals_escalated', to='accounts.user')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appeals_reviewed', to='accounts.user')),
                ('submitted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appeals_submitted', to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

