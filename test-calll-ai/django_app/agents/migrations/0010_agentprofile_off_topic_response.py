from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0009_tenantlivecontext'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentprofile',
            name='off_topic_response',
            field=models.TextField(
                blank=True,
                default='',
                verbose_name='رسالة الرد خارج النطاق',
                help_text=(
                    'الرسالة التي يرددها المساعد عندما يسأله العميل سؤالاً خارج نطاق عمله. '
                    'مثال: «بعتذر جداً يا فندم، أنا بساعدك بس في طلبات مطعم ضيافة، '
                    'تحب تطلب حاجة؟» — إذا تُركت فارغة يُستخدم رد افتراضي.'
                ),
            ),
        ),
    ]
