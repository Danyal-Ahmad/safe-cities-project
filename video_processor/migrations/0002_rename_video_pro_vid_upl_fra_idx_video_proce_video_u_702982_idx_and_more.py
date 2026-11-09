

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('video_processor', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='videoframe',
            new_name='video_proce_video_u_702982_idx',
            old_name='video_pro_vid_upl_fra_idx',
        ),
        migrations.RenameIndex(
            model_name='videoframe',
            new_name='video_proce_plate_d_e6427c_idx',
            old_name='video_pro_pla_det_aut_idx',
        ),
        migrations.AlterField(
            model_name='videoupload',
            name='uploaded_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='video_uploads', to=settings.AUTH_USER_MODEL),
        ),
    ]

