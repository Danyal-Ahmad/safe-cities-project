
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('detections', '0003_rename_detections_det_stat_cre_idx_detections__status_672746_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('box', 'Bounding Box'), ('polygon', 'Polygon'), ('line', 'Line'), ('marker', 'Marker'), ('violation', 'Violation Marker')], default='box', max_length=20)),
                ('object_type', models.CharField(choices=[('vehicle', 'Vehicle'), ('plate', 'License Plate'), ('person', 'Person'), ('other', 'Other')], default='vehicle', max_length=20)),
                ('violation_type', models.CharField(blank=True, choices=[('wrong_way', 'Wrong Way'), ('signal_break', 'Signal Break'), ('over_speed', 'Over Speed'), ('no_helmet', 'No Helmet'), ('other', 'Other')], help_text='Set when type=violation. Records which violation the marker represents.', max_length=20, null=True)),
                ('label', models.CharField(blank=True, default='', help_text='Human-readable label for the annotation.', max_length=100)),
                ('coordinates', models.JSONField(blank=True, default=dict, help_text='Box: {x, y, width, height}. Polygon/Line: [[x,y],...]. Marker: {x, y}.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='annotations_created', to=settings.AUTH_USER_MODEL)),
                ('detection', models.ForeignKey(help_text='The detection/frame this annotation belongs to. Ties the annotation to the tracked vehicle.', on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to='detections.detection')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['detection', 'created_at'], name='detections__detecti_f4276b_idx'), models.Index(fields=['type'], name='detections__type_c88fbf_idx'), models.Index(fields=['object_type'], name='detections__object__88d049_idx')],
            },
        ),
    ]
