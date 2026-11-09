from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('accounts', '0005_drop_custom_permissions')]
    operations = [
        migrations.AlterModelTable(name='user', table='sc_users'),
        migrations.AlterModelTable(name='officerprofile', table='sc_officer_profiles'),
        migrations.AlterModelTable(name='vehicleregistration', table='sc_vehicle_registrations'),
        migrations.AlterModelTable(name='passwordresettoken', table='sc_password_reset_tokens'),
    ]
