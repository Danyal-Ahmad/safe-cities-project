from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('video_processor', '0003_videoupload_camera')]
    operations = [
        migrations.AlterModelTable(name='videoupload', table='sc_video_uploads'),
        migrations.AlterModelTable(name='videoframe', table='sc_video_frames'),
    ]
