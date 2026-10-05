from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('call_center', '0007_alter_employeecalllog_recording_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeprofile',
            name='wazo_user_uuid',
            field=models.CharField(blank=True, default='', help_text='معرف المستخدم في سنترال Wazo', max_length=128),
        ),
        migrations.AddField(
            model_name='employeeprofile',
            name='wazo_line_id',
            field=models.CharField(blank=True, default='', help_text='معرف الخط في سنترال Wazo', max_length=128),
        ),
        migrations.AddField(
            model_name='employeeprofile',
            name='sip_username',
            field=models.CharField(blank=True, default='', help_text='اسم مستخدم الـ SIP للهاتف المكتبي أو التطبيق', max_length=128),
        ),
        migrations.AddField(
            model_name='employeeprofile',
            name='sip_password',
            field=models.CharField(blank=True, default='', help_text='كلمة مرور الـ SIP', max_length=128),
        ),
        migrations.AddField(
            model_name='employeeprofile',
            name='sip_host',
            field=models.CharField(blank=True, default='', help_text='عنوان سيرفر الـ SIP', max_length=128),
        ),
        migrations.AddField(
            model_name='employeeprofile',
            name='sip_port',
            field=models.PositiveIntegerField(default=5070, help_text='منفذ سنترال Wazo'),
        ),
        migrations.AddField(
            model_name='callqueue',
            name='wazo_queue_id',
            field=models.CharField(blank=True, default='', help_text='معرف الطابور في سنترال Wazo', max_length=128),
        ),
    ]
