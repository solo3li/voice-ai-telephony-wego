from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from voice_assistant.models import AgentProfile

class Command(BaseCommand):
    help = 'Pre-seed diverse default agent profiles (dialects, voices, personas) for user hamo'

    def handle(self, *args, **options):
        hamo = User.objects.filter(username='hamo').first()
        if not hamo:
            self.stdout.write(self.style.ERROR("User 'hamo' does not exist."))
            return

        presets = [
            {
                "name": "نورهان - خدمة عملاء مصرية",
                "voice_name": "Aoede",
                "gender": "female",
                "dialect": "egyptian",
                "persona_role": "customer_support",
                "speaking_style": "friendly",
                "custom_instructions": "خليكي دايماً لطيفة وبنت بلد ومبتسمة وقولي يا فندم ويا باشا.",
                "is_active": True,
            },
            {
                "name": "فهد - مستشار مبيعات سعودي",
                "voice_name": "Puck",
                "gender": "male",
                "dialect": "saudi",
                "persona_role": "sales_advisor",
                "speaking_style": "enthusiastic",
                "custom_instructions": "استخدم عبارات الترحيب السعودية زي أبشر وسم وطال عمرك ويا هلا والله.",
                "is_active": False,
            },
            {
                "name": "سارة - مساعدة رسمية بالفصحى",
                "voice_name": "Kore",
                "gender": "female",
                "dialect": "fusha",
                "persona_role": "technical_consultant",
                "speaking_style": "formal",
                "custom_instructions": "تحدثي بلغة عربية فصحى معاصرة واضحة وبنبرة مهنية ورسمية رفيعة.",
                "is_active": False,
            },
            {
                "name": "كريم - دعم فني شامي",
                "voice_name": "Charon",
                "gender": "male",
                "dialect": "levantine",
                "persona_role": "personal_assistant",
                "speaking_style": "concise",
                "custom_instructions": "تحدث باللهجة الشامية اللطيفة وكن مختصراً وسريع الإنجاز (مثل: تكرم عينك، على راسي).",
                "is_active": False,
            },
        ]

        for p in presets:
            prof, created = AgentProfile.objects.update_or_create(
                user=hamo,
                name=p["name"],
                defaults=p
            )
            state = "Created" if created else "Updated"
            self.stdout.write(f"  {state} profile: {prof.name}")

        self.stdout.write(self.style.SUCCESS("Successfully seeded agent profiles for 'hamo'!"))
