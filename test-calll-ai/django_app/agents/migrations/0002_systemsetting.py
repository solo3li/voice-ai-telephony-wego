from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gemini_api_key', models.CharField(blank=True, default='', help_text='المفتاح المركزي لخدمات Google Gemini Live ونظام الـ RAG الصوتي', max_length=255, verbose_name='Google Gemini API Key')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'إعدادات النظام العامة',
                'verbose_name_plural': 'إعدادات النظام العامة',
                'db_table': 'voice_assistant_systemsetting',
            },
        ),
        migrations.AlterField(
            model_name='usermcpserver',
            name='name',
            field=models.CharField(default='خادم أدوات خارجي (FastMCP)', max_length=100),
        ),
        migrations.AlterField(
            model_name='usermcpserver',
            name='server_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
