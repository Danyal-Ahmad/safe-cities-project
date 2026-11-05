
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appeals', '0005_alter_challanappeal_current_stage'),
    ]

    operations = [
        migrations.AddField(
            model_name='challanappeal',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
