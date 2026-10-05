import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telephony', '0003_businesshoursschedule'),
        ('agents', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantDID',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(db_index=True, help_text='رقم الهاتف بصيغة E.164 (مثل +20108124794)', max_length=64, unique=True)),
                ('label', models.CharField(blank=True, default='', help_text='تسمية توضيحية للرقم (مثل: خط الدعم الرئيسي)', max_length=128)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('target_profile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='did_mappings', to='agents.agentprofile')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dids', to=settings.AUTH_USER_MODEL, verbose_name='المستأجر / الشركة')),
            ],
            options={
                'verbose_name': 'رقم خط المستأجر (DID)',
                'verbose_name_plural': 'أرقام خطوط المستأجرين (DIDs)',
                'db_table': 'voice_assistant_tenantdid',
                'ordering': ['-created_at'],
            },
        ),
    ]
