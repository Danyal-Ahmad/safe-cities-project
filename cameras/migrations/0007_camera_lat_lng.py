from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0006_professional_table_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='camera',
            name='latitude',
            field=models.FloatField(blank=True, help_text='GPS latitude for map/heatmap (optional).', null=True),
        ),
        migrations.AddField(
            model_name='camera',
            name='longitude',
            field=models.FloatField(blank=True, help_text='GPS longitude for map/heatmap (optional).', null=True),
        ),
    ]

