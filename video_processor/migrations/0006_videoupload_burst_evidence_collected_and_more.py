

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('video_processor', '0005_rename_video_proce_video_u_702982_idx_sc_video_fr_video_u_765af3_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='videoupload',
            name='burst_evidence_collected',
            field=models.IntegerField(default=0, help_text='Tracks that collected the required 3-frame evidence via 90fps-density burst sampling.'),
        ),
        migrations.AddField(
            model_name='videoupload',
            name='file_sha256',
            field=models.CharField(blank=True, help_text='Tamper-evident digest of the uploaded video file.', max_length=64, null=True),
        ),
    ]

