from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('realtime', '0002_alter_cameraassignment_assigned_by')]
    operations = [
        migrations.AlterModelTable(name='livefeed', table='sc_live_feeds'),
        migrations.AlterModelTable(name='cameraassignment', table='sc_camera_assignments'),
    ]
