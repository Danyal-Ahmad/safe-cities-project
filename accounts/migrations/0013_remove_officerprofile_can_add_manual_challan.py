

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_alter_adminpasswordresetrequest_id_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='officerprofile',
            name='can_add_manual_challan',
        ),
    ]
