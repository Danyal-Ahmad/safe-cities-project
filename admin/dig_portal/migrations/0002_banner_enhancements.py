


import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dig_portal', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        migrations.AddField(
            model_name='banner',
            name='banner_type',
            field=models.CharField(
                choices=[('image', 'Image Banner'), ('html', 'Custom HTML/Code')],
                default='image', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='banner',
            name='image',
            field=models.ImageField(
                blank=True, help_text='Upload banner image',
                null=True, upload_to='banners/',
            ),
        ),
        migrations.AddField(
            model_name='banner',
            name='image_link',
            field=models.URLField(
                blank=True, default='',
                help_text='URL to open when banner is clicked',
                max_length=500,
            ),
        ),


        migrations.AlterField(
            model_name='alert',
            name='created_by',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='alerts_created', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='actor',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='audit_entries', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='banner',
            name='audience',
            field=models.CharField(
                choices=[
                    ('all', 'Everyone'), ('staff', 'All Staff'),
                    ('citizens', 'All Citizens'), ('dig', 'DIG only'),
                    ('ssp', 'SSP only'), ('supervisor', 'Supervisors only'),
                    ('officer', 'Officers only'), ('audit', 'Audit Officers only'),
                    ('it', 'IT Support only'),
                ],
                default='all', max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='banner',
            name='created_by',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='banners_created', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='banner',
            name='html_content',
            field=models.TextField(
                blank=True, default='',
                help_text='Raw HTML content (for custom code banners)',
            ),
        ),
        migrations.AlterField(
            model_name='banner',
            name='placement',
            field=models.CharField(
                choices=[
                    ('top', 'Top of page'), ('bottom', 'Bottom of page'),
                    ('ad', 'Home page ad slot'), ('popup', 'Popup ad (modal)'),
                ],
                default='top', max_length=10,
            ),
        ),
    ]
