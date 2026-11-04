from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('cameras', '0005_alter_camera_auto_confirm_threshold')]
    operations = [
        migrations.AlterModelTable(name='camera', table='sc_cameras'),
    ]
