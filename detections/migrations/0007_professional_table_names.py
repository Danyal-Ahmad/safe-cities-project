from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('detections', '0006_alter_detection_camera')]
    operations = [
        migrations.AlterModelTable(name='detection', table='sc_detections'),
        migrations.AlterModelTable(name='detectionreviewnote', table='sc_detection_review_notes'),
        migrations.AlterModelTable(name='annotation', table='sc_annotations'),
    ]

