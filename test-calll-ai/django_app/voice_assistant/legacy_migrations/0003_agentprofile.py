from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('voice_assistant', '0002_useraction'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='البروفايل الافتراضي', max_length=100)),
                ('voice_name', models.CharField(default='Aoede', max_length=50)),
                ('gender', models.CharField(choices=[('female', 'أنثى'), ('male', 'ذكر')], default='female', max_length=20)),
                ('dialect', models.CharField(choices=[('egyptian', 'لهجة مصرية عامية'), ('saudi', 'لهجة خليجية / سعودية'), ('levantine', 'لهجة شامية'), ('fusha', 'عربية فصحى معاصرة'), ('english', 'English')], default='egyptian', max_length=50)),
                ('persona_role', models.CharField(choices=[('customer_support', 'خدمة عملاء ومبيعات المتجر'), ('sales_advisor', 'مستشار تسويق ومبيعات شاطر'), ('personal_assistant', 'مساعد شخصي ذكي وودود'), ('technical_consultant', 'مستشار فني ورسمي')], default='customer_support', max_length=50)),
                ('speaking_style', models.CharField(choices=[('friendly', 'ودود ولطيف ومرح'), ('formal', 'رسمي وهادئ ورصين'), ('concise', 'مباشر وسريع وموجز'), ('enthusiastic', 'حماسي وتشجيعي')], default='friendly', max_length=50)),
                ('custom_instructions', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='agent_profiles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
