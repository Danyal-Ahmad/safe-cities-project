"""Add avatar ImageField to User."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.ImageField(blank=True, help_text='Optional profile picture upload.', null=True, upload_to='avatars/'),
        ),
    ]
