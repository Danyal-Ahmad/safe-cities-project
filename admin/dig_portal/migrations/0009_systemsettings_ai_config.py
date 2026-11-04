from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('dig_portal', '0008_challantemplate'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='ai_config',
            field=models.JSONField(blank=True, default=dict, help_text='ONNX model runtime settings (input sizes, thresholds, class filters)'),
        ),
        migrations.AlterField(
            model_name='systemsettings',
            name='ai_confidence_threshold',
            field=models.FloatField(default=0.9, help_text='Minimum confidence to accept a car detection (model default target 0.90)'),
        ),
    ]
