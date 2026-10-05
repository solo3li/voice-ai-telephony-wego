from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('voice_assistant', '0011_remove_queuemembership_sip_account_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='UserAction',
        ),
    ]
