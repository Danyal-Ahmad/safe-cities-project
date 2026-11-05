"""challans migration 0001 - Challan model."""
import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
        ('cameras', '0001_initial'),
        ('detections', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Challan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ticket_no', models.CharField(editable=False, max_length=30, unique=True)),
                ('plate_number', models.CharField(max_length=20)),
                ('province', models.CharField(blank=True, max_length=10, null=True)),
                ('owner_name', models.CharField(blank=True, max_length=255, null=True)),
                ('cnic', models.CharField(blank=True, max_length=20, null=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('vehicle_type', models.CharField(blank=True, max_length=20, null=True)),
                ('make_year', models.CharField(blank=True, max_length=4, null=True)),
                ('color', models.CharField(blank=True, max_length=20, null=True)),
                ('chassis_no', models.CharField(blank=True, max_length=50, null=True)),
                ('violation_type', models.CharField(choices=[('wrong_way', 'Wrong Way'), ('no_helmet', 'No Helmet'), ('signal_break', 'Signal Break'), ('over_speed', 'Over Speed'), ('other', 'Other')], default='wrong_way', max_length=20)),
                ('fine_amount', models.DecimalField(decimal_places=2, default=500, max_digits=10)),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
                ('ai_confidence', models.FloatField(blank=True, null=True)),
                ('moving_direction', models.CharField(blank=True, max_length=10, null=True)),
                ('legal_direction', models.CharField(blank=True, max_length=10, null=True)),
                ('issue_date', models.DateField(default=datetime.date.today)),
                ('due_date', models.DateField()),
                ('payment_status', models.CharField(choices=[('UNPAID', 'Unpaid'), ('PAID', 'Paid'), ('VOIDED', 'Voided')], default='UNPAID', max_length=10)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='challans/pdfs/%Y/%m/%d/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('camera', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='cameras.camera')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='challans_created', to='accounts.user')),
                ('detection', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='challans', to='detections.detection')),
            ],
            options={
                'ordering': ['-issue_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='challan',
            index=models.Index(fields=['cnic'], name='challans_cha_cnic_idx'),
        ),
        migrations.AddIndex(
            model_name='challan',
            index=models.Index(fields=['plate_number'], name='challans_cha_plate_idx'),
        ),
        migrations.AddIndex(
            model_name='challan',
            index=models.Index(fields=['payment_status'], name='challans_cha_payme_idx'),
        ),
        migrations.AddIndex(
            model_name='challan',
            index=models.Index(fields=['issue_date'], name='challans_cha_issue_idx'),
        ),
    ]
