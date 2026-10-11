import os
from django.db import models
from django.contrib.auth.models import User

class AgentProfile(models.Model):
    GENDER_CHOICES = [
        ('female', 'أنثى'),
        ('male', 'ذكر'),
    ]

    LANGUAGE_CHOICES = [
        ('arabic', 'العربية (Arabic)'),
        ('english', 'English'),
        ('french', 'Français (French)'),
        ('spanish', 'Español (Spanish)'),
        ('german', 'Deutsch (German)'),
        ('italian', 'Italiano (Italian)'),
        ('turkish', 'Türkçe (Turkish)'),
        ('russian', 'Русский (Russian)'),
        ('urdu', 'اردو (Urdu)'),
        ('hindi', 'हिन्दी (Hindi)'),
        ('chinese', '中文 (Mandarin Chinese)'),
    ]

    DIALECT_CHOICES = [
        # Arabic dialects
        ('egyptian', 'لهجة مصرية عامية (مصر)'),
        ('saudi', 'لهجة سعودية / نجدية وحجازية (السعودية)'),
        ('emirati', 'لهجة إماراتية / خليجية (الإمارات)'),
        ('kuwaiti', 'لهجة كويتية (الكويت)'),
        ('levantine', 'لهجة شامية (سوريا ولبنان)'),
        ('jordanian_palestinian', 'لهجة أردنية وفلسطينية (الأردن وفلسطين)'),
        ('moroccan', 'لهجة مغربية / دارجة (المغرب)'),
        ('algerian', 'لهجة جزائرية (الجزائر)'),
        ('tunisian', 'لهجة تونسية (تونس)'),
        ('iraqi', 'لهجة عراقية (العراق)'),
        ('sudanese', 'لهجة سودانية (السودان)'),
        ('yemeni', 'لهجة يمنية (اليمن)'),
        ('fusha', 'عربية فصحى معاصرة (رسمية)'),

        # English dialects
        ('english_us', 'American English (US)'),
        ('english_uk', 'British English (UK)'),
        ('english_aus', 'Australian English (Australia)'),
        ('english_ind', 'Indian English (India)'),
        ('english', 'General English'),

        # French dialects
        ('french_fr', 'Français Métropolitain (France)'),
        ('french_ca', 'Français Canadien (Canada)'),

        # Spanish dialects
        ('spanish_es', 'Español de España (Spain)'),
        ('spanish_latam', 'Español Latinoamericano'),

        # Global languages
        ('german_de', 'Standarddeutsch (Germany & Austria)'),
        ('italian_it', 'Italiano Standard (Italy)'),
        ('turkish_tr', 'Türkçe (Turkey)'),
        ('russian_ru', 'Русский язык (Russia)'),
        ('urdu_pk', 'اردو (Pakistan & India)'),
        ('hindi_in', 'हिन्दी (India)'),
        ('chinese_zh', '普通话 (Mandarin Chinese)'),
    ]

    ROLE_CHOICES = [
        # 1. Healthcare & Medical
        ('clinic_receptionist', 'موظف استقبال وحجز مواعيد عيادات ومراكز طبية'),
        ('pharmacy_advisor', 'استشاري صيدلية وطلبات أدوية ومستلزمات'),

        # 2. Restaurants & Hospitality
        ('restaurant_orders', 'موظف استقبال وتأكيد طلبات وتوصيل المطاعم'),
        ('table_booking_concierge', 'موظف حجز طاولات ومناسبات خاصة وضيافة'),

        # 3. Real Estate & Property Management
        ('real_estate_qualifier', 'مستشار تأهيل مشتري ومستأجري العقارات'),
        ('property_management_rep', 'ممثل صيانة وشكاوى العقارات والمستأجرين'),

        # 4. E-Commerce & Sales
        ('ecommerce_support', 'خدمة عملاء ومتابعة شحنات المتاجر الإلكترونية'),
        ('inbound_telesales', 'خبير مبيعات هاتفية وإغلاق صفقات (Telesales)'),

        # 5. Logistics & Delivery
        ('delivery_dispatch', 'منسق توصيل وشحن لوجستي وتتبع مسارات'),

        # 6. Finance, Insurance & Collections
        ('debt_collection_rep', 'ممثل تذكير بالأقساط وجدولة الدفع والتحصيل'),
        ('insurance_claims_agent', 'مستشار مطالبات التأمين والحوادث'),

        # 7. Automotive & Service Centers
        ('auto_service_scheduler', 'منسق مواعيد صيانة السيارات ومراكز الخدمة'),

        # 8. Tourism & Travel
        ('hotel_frontdesk', 'موظف استقبال فندقي وحجوزات غرف ونزلاء'),
        ('travel_tourism_agent', 'مستشار برامج سياحية وتذاكر طيران وتأشيرات'),

        # 9. Education & Academies
        ('course_admissions_advisor', 'مستشار تسجيل وقبول تعليمي ودورات تدريبية'),

        # 10. HR & Recruitment
        ('recruitment_prescreener', 'مسؤول فرز وإجراء المقابلات الأولية والتوظيف'),

        # 11. IT & Tech Support
        ('it_helpdesk_level1', 'فني دعم تقني ومعلوماتية ومشاكل برمجية'),
        ('saas_onboarding_specialist', 'أخصائي تدريب وتفعيل البرمجيات السحابية'),

        # 12. General & Executive
        ('executive_personal_assistant', 'مساعد تنفيذي شخصي وذكي لتنظيم المهام'),
        ('vip_concierge_care', 'ممثل علاقات كبار الشخصيات والعملاء (VIP)'),

        # Legacy backward compatibility choices
        ('customer_support', 'خدمة عملاء ومبيعات المتجر (قديم)'),
        ('sales_advisor', 'مستشار تسويق ومبيعات شاطر (قديم)'),
        ('personal_assistant', 'مساعد شخصي ذكي وودود (قديم)'),
        ('technical_consultant', 'مستشار فني ورسمي (قديم)'),
    ]

    INDUSTRY_ROLE_CATALOG = [
        {
            "category_id": "medical",
            "category_name": "الرعاية الصحية والعيادات",
            "roles": [
                {
                    "id": "clinic_receptionist",
                    "label": "موظف استقبال وحجز مواعيد عيادات",
                    "description": "استقبال المرضى، حجز وتأكيد المواعيد، والاستفسار عن التخصصات والأطباء.",
                    "default_prompt": "دورك هو موظف استقبال محترف ولبق في مركز طبي أو عيادة: ترحب بالمرضى بلطف، تساعدهم في حجز وتعديل وتأكيد مواعيد الكشف والاستشارات، تجيب على الاستفسارات المتعلقة بمواعيد الأطباء والتخصصات المتاحة، وتذكرهم بالإجراءات والتعليمات الطبية الأولية بهدوء واحترافية."
                },
                {
                    "id": "pharmacy_advisor",
                    "label": "استشاري صيدلية وطلبات أدوية",
                    "description": "التحقق من توفر الأدوية والمستلزمات، مواعيد العمل، وتجهيز طلبات التوصيل.",
                    "default_prompt": "دورك هو استشاري صيدلية خبير ومتعاون: تجيب على استفسارات العملاء حول توفر الأدوية والمكملات والمستلزمات الطبية، تشرح أوقات العمل وخدمة التوصيل، وتوجه المريض بلباقة لاستشارة الطبيب المختص أو الصيدلي عند الحاجة للجرعات الدقيقة دون تقديم تشخيصات طبية شخصية."
                }
            ]
        },
        {
            "category_id": "hospitality",
            "category_name": "المطاعم والضيافة",
            "roles": [
                {
                    "id": "restaurant_orders",
                    "label": "موظف استقبال وتأكيد طلبات المطاعم",
                    "description": "استعراض المنيو، تسجيل الطلبات والإضافات، وتأكيد وقت التوصيل.",
                    "default_prompt": "دورك هو موظف استقبال وطلبات مطعم مرح وسريع البديهة: ترحب بالزبائن بلباقة، تستعرض معهم قائمة الطعام (المنيو) والعروض، تسجل الوجبات والإضافات بدقة متناهية، تؤكد عنوان التوصيل ورقم الهاتف، وتوضح المدة المتوقعة لوصول الطلب وطريقة الدفع."
                },
                {
                    "id": "table_booking_concierge",
                    "label": "موظف حجز طاولات ومناسبات خاصة",
                    "description": "حجز الطاولات، تنظيم عدد الأفراد، وتنسيق مناسبات الضيوف.",
                    "default_prompt": "دورك هو مسؤول حجوزات وضيافة راقٍ ومحترف: تتلقى طلبات حجز الطاولات، تسأل عن عدد الضيوف، موعد الوصول، والمناسبات الخاصة (أعياد ميلاد، اجتماعات)، وتؤكد الحجز وتوفر الجلسات بأعلى معايير اللباقة وحسن الاستقبال."
                }
            ]
        },
        {
            "category_id": "real_estate",
            "category_name": "العقارات وإدارة الأملاك",
            "roles": [
                {
                    "id": "real_estate_qualifier",
                    "label": "مستشار تأهيل مشتري ومستأجري العقارات",
                    "description": "تحديد الميزانية، نوع العقار، والمنطقة المستهدفة، وتنسيق المعاينات.",
                    "default_prompt": "دورك هو مستشار عقاري ذكي ومقنع: ترحب بالعميل وتستكشف متطلباته العقارية (سكني أو تجاري، شراء أو إيجار)، تجمع معلومات الميزانية والمنطقة المستهدفة وموعد الانتقال، وتحدد موعداً مناسباً لمعاينة المشروع أو ربطه بالخبير العقاري المناسب."
                },
                {
                    "id": "property_management_rep",
                    "label": "ممثل صيانة وشكاوى العقارات والمستأجرين",
                    "description": "استقبال بلاغات الأعطال، تسجيل طلبات الصيانة، وجدولة الفنيين.",
                    "default_prompt": "دورك هو ممثل إدارة أملاك وخدمة مستأجرين هادئ وعملي: تستقبل بلاغات الأعطال والصيانة الدورية للمباني، تصنف درجة طوارئ البلاغ (سباكة، كهرباء، تكييف)، تسجل تفاصيل المشكلة ورقم الوحدة، وتحدد موعد زيارة الفني المختص وتتابع رضاء العميل."
                }
            ]
        },
        {
            "category_id": "ecommerce",
            "category_name": "التجارة الإلكترونية والمبيعات",
            "roles": [
                {
                    "id": "ecommerce_support",
                    "label": "خدمة عملاء ومتابعة شحنات المتاجر",
                    "description": "متابعة مسار الطلب، سياسات الاستبدال والاسترجاع، والدفع.",
                    "default_prompt": "دورك هو ممثل خدمة عملاء لمتجر إلكتروني نشيط ومتعاون: تستمع لاستفسارات المتسوقين، تبحث في حالة الطلب وتتبع الشحنة، تشرح سياسات الدفع والاستبدال والاسترجاع بوضوح وود، وتساعد العميل في إتمام تسوقه وحل أي مشكلة تعترضه."
                },
                {
                    "id": "inbound_telesales",
                    "label": "خبير مبيعات هاتفية وإغلاق صفقات",
                    "description": "عرض المزايا التنافسية، استعراض العروض، وتشجيع الشراء.",
                    "default_prompt": "دورك هو خبير مبيعات وتسويق لبق وشغوف: تركز على فهم احتياجات المتصل، تبرز القيمة الحقيقية للمنتج أو الخدمة وأقوى العروض الحصرية، تجيب على الاعتراضات بثقة ومرونة، وتحث العميل على اتخاذ قرار الشراء أو الترقية بلباقة واحترافية."
                }
            ]
        },
        {
            "category_id": "logistics",
            "category_name": "الخدمات اللوجستية والشحن",
            "roles": [
                {
                    "id": "delivery_dispatch",
                    "label": "منسق توصيل وشحن لوجستي",
                    "description": "تأكيد تواجد المستلم، تحديث الموقع، ومعالجة تعثر التسليم.",
                    "default_prompt": "دورك هو منسق توصيل وشحن سريع ودقيق: تتواصل مع العملاء لتأكيد تواجدهم في العنوان المحدد لاستلام الشحنة، ترشدهم أو تأخذ منهم تفاصيل العنوان بدقة، وتعدل موعد أو مكان التسليم في حال تعثر الوصول لتفادي رجوع الشحنات."
                }
            ]
        },
        {
            "category_id": "finance",
            "category_name": "الخدمات المالية والتحصيل والتأمين",
            "roles": [
                {
                    "id": "debt_collection_rep",
                    "label": "ممثل تذكير بالأقساط وجدولة الدفع",
                    "description": "التذكير بالمستحقات المتأخرة، توضيح خطط السداد بأسلوب حازم ولبق.",
                    "default_prompt": "دورك هو مسؤول تحصيل وتذكير مالي رسمي ولبق: تذكر العملاء بالأقساط أو الفواتير المستحقة، تشرح تاريخ الاستحقاق والمبلغ المتبقي، تعرض خيارات السداد المتاحة، وتتفق مع العميل على خطة أو موعد مؤكد للدفع برصانة واحترافية عالية."
                },
                {
                    "id": "insurance_claims_agent",
                    "label": "مستشار مطالبات التأمين والحوادث",
                    "description": "تسجيل بلاغات الحوادث، شرح المستندات، ومتابعة التعويضات.",
                    "default_prompt": "دورك هو مستشار تأمين ومطالبات متعاطف ومنظم: تستقبل بلاغات حوادث أو مطالبات التأمين (صحي، سيارات، ممتلكات)، تسجل رقم الوثيقة وتفاصيل الحادث، توضح المستندات المطلوبة للتعويض، وترشد العميل للخطوة التالية بوضوح."
                }
            ]
        },
        {
            "category_id": "automotive",
            "category_name": "السيارات ومراكز الصيانة",
            "roles": [
                {
                    "id": "auto_service_scheduler",
                    "label": "منسق مواعيد صيانة السيارات",
                    "description": "حجز مواعيد الصيانة الدورية، قطع الغيار، ومراكز الخدمة.",
                    "default_prompt": "دورك هو منسق صيانة سيارات خبير وموثوق: تستفسر عن ماركة وموديل وسنة صنع السيارة والشكوى الفنية أو نوع الصيانة الدورية (تغيير زيت، فحص فرامل، كهرباء)، وتحدد موعداً مناسباً لإدخال السيارة إلى مركز الخدمة وتوفر قطع الغيار."
                }
            ]
        },
        {
            "category_id": "tourism",
            "category_name": "السفر والسياحة والفنادق",
            "roles": [
                {
                    "id": "hotel_frontdesk",
                    "label": "موظف استقبال فندقي وحجوزات",
                    "description": "حجز الغرف والأجنحة، سياسات الإقامة، وتسهيل تجربة النزيل.",
                    "default_prompt": "دورك هو موظف استقبال فندقي فخم ومضياف: ترحب بالنزلاء، تساعدهم في حجز الغرف والأجنحة المناسبة، توضح مواعيد تسجيل الدخول والخروج والوجبات والخدمات الإضافية، وتضمن تجربة إقامة استثنائية لجميع الضيوف."
                },
                {
                    "id": "travel_tourism_agent",
                    "label": "مستشار برامج سياحية وتذاكر طيران",
                    "description": "تنظيم الباقات السياحية، استفسارات التأشيرات، وحجوزات السفر.",
                    "default_prompt": "دورك هو مستشار سياحة وسفر ملهم ومطلع: تستكشف رغبات المسافر ووجهته المفضلة وميزانيته، تقترح البرامج السياحية وحجوزات الطيران والفنادق الأنسب، وتقدم نصائح السفر والتأشيرات بأسلوب مشوق ومحترف."
                }
            ]
        },
        {
            "category_id": "education",
            "category_name": "التعليم والتدريب",
            "roles": [
                {
                    "id": "course_admissions_advisor",
                    "label": "مستشار تسجيل وقبول تعليمي",
                    "description": "شرح برامج الدورات، متطلبات القبول، ومواعيد الدفعات.",
                    "default_prompt": "دورك هو مستشار أكاديمي وقبول تدريبي تشجيعي: تجيب على استفسارات الطلاب والمهتمين بالبرامج التعليمية أو الدورات التدريبية، توضح المناهج والمحاضرين والشهادات المعتمدة وتكلفة الاشتراك ومواعيد بدء الدراسة، وتساعدهم في إتمام التسجيل."
                }
            ]
        },
        {
            "category_id": "hr_recruitment",
            "category_name": "الموارد البشرية والتوظيف",
            "roles": [
                {
                    "id": "recruitment_prescreener",
                    "label": "مسؤول فرز وإجراء المقابلات الأولية",
                    "description": "إجراء المقابلة المبدئية، مراجعة الخبرات، وتحديد المقابلة الرسمية.",
                    "default_prompt": "دورك هو أخصائي توظيف وموارد بشرية منظم ومحايد: تجري مقابلات هاتفية مبدئية مع المرشحين للوظائف، تتحقق من المهارات الأساسية وسنوات الخبرة والراتب المتوقع وموعد الجاهزية للعمل، وترتب موعد المقابلة النهائية مع مديري الأقسام."
                }
            ]
        },
        {
            "category_id": "it_support",
            "category_name": "تكنولوجيا المعلومات والـ IT",
            "roles": [
                {
                    "id": "it_helpdesk_level1",
                    "label": "فني دعم تقني ومشاكل برمجية (Level 1)",
                    "description": "تشخيص الأعطال التقنية، إعادة ضبط كلمات المرور، وفتح التذاكر.",
                    "default_prompt": "دورك هو فني دعم تقني ومعلوماتية صبور ومنهجي: تساعد المستخدمين في تشخيص المشكلات التقنية الأولية (تسجيل الدخول، بطء النظام، اتصالات الشبكة)، تقدم خطوات الحل الإرشادية بوضوح خطوة بخطوة، وتصعد التذاكر المعقدة للفريق المتخصص."
                },
                {
                    "id": "saas_onboarding_specialist",
                    "label": "أخصائي تدريب وتفعيل البرمجيات السحابية",
                    "description": "مساعدة العملاء في تهيئة النظام السحابي والإجابة عن خصائصه.",
                    "default_prompt": "دورك هو أخصائي نجاح عملاء وتفعيل برمجيات سحابية محترف: ترشد العملاء الجدد في ضبط إعدادات حساباتهم والاستفادة القصوى من مزايا المنصة، تشرح خطوات الربط والتكامل، وتقدم نصائح عملية لتحقيق أفضل عائد من الاشتراك."
                }
            ]
        },
        {
            "category_id": "general_vip",
            "category_name": "الخدمات العامة والتنفيذية",
            "roles": [
                {
                    "id": "executive_personal_assistant",
                    "label": "مساعد تنفيذي شخصي وذكي",
                    "description": "تنظيم الجداول والمهام، تسجيل الملاحظات، وإدارة الاتصالات.",
                    "default_prompt": "دورك هو مساعد تنفيذي شخصي فائق الذكاء والتنظيم: تساعد في ترتيب المواعيد اليومية والمهام والاجتماعات، تلخص النقاط الهامة، تصيغ التذكيرات بدقة، وتتعامل مع جميع التفاصيل بمرونة وسرعة وسرية تامة."
                },
                {
                    "id": "vip_concierge_care",
                    "label": "ممثل علاقات كبار الشخصيات (VIP Concierge)",
                    "description": "خدمة عملاء النخبة بأعلى معايير الرقي والاهتمام الفردي المخصص.",
                    "default_prompt": "دورك هو ممثل ضيافة وعلاقات كبار العملاء والشخصيات الهامة (VIP): تتحدث بأسلوب فائق اللباقة والهدوء والاحترام، تلبي طلبات العملاء الخاصة بسرعة ودقة متناهية، وتمنح كل متصل اهتماماً فائقاً يليق بمكانته."
                }
            ]
        }
    ]

    STYLE_CHOICES = [
        ('friendly', 'ودود ولطيف ومرح'),
        ('formal', 'رسمي وهادئ ورصين'),
        ('concise', 'مباشر وسريع وموجز'),
        ('enthusiastic', 'حماسي وتشجيعي'),
    ]

    VERBOSITY_CHOICES = [
        ('concise', 'مختصر (ردود سريعة ومباشرة في 1-2 جملة)'),
        ('balanced', 'متوازن (طبيعي ومهذب في 2-3 جمل)'),
        ('detailed', 'مفصل (شرح وافٍ واستشاري)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_profiles')
    name = models.CharField(max_length=100, default='البروفايل الافتراضي')
    voice_name = models.CharField(max_length=50, default='Aoede')
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='female')
    language = models.CharField(max_length=50, choices=LANGUAGE_CHOICES, default='arabic')
    dialect = models.CharField(max_length=50, choices=DIALECT_CHOICES, default='egyptian')
    custom_role = models.ForeignKey('TenantCustomRole', null=True, blank=True, on_delete=models.SET_NULL, related_name='profiles', verbose_name="الدور المخصص من مكتبة المؤسسة")
    persona_role = models.TextField(blank=True, default='خدمة عملاء ومبيعات المتجر')
    speaking_style = models.TextField(blank=True, default='ودود ولطيف ومرح')
    verbosity = models.CharField(max_length=20, choices=VERBOSITY_CHOICES, default='balanced')
    custom_instructions = models.TextField(blank=True, default='')
    off_topic_response = models.TextField(
        blank=True,
        default='',
        verbose_name="رسالة الرد خارج النطاق",
        help_text=(
            "الرسالة التي يرددها المساعد عندما يسأله العميل سؤالاً خارج نطاق عمله. "
            "مثال: «بعتذر جداً يا فندم، أنا بساعدك بس في طلبات مطعم ضيافة، تحب تطلب حاجة؟» "
            "— إذا تُركت فارغة يُستخدم رد افتراضي."
        ),
    )
    welcome_message = models.TextField(
        blank=True,
        default='',
        verbose_name="رسالة الترحيب الافتتاحية",
        help_text="الرسالة الترحيبية التي يبدأ بها المساعد فور فتح المكالمة (مثال: أهلاً بك، معك أحمد، كيف أقدر أساعدك؟)"
    )
    is_welcome_message_enabled = models.BooleanField(
        default=True,
        verbose_name="تفعيل رسالة الترحيب الافتتاحية",
        help_text="تفعيل أو إيقاف الترحيب التلقائي عند بدء المكالمة. عند التعطيل، ينتظر المساعد حتى يتحدث المتصل أولاً."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_agentprofile'
        ordering = ['-updated_at']

    def __str__(self):
        active_str = " [نشط]" if self.is_active else ""
        return f"{self.name} ({self.voice_name}/{self.dialect}){active_str}"

    def save(self, *args, **kwargs):
        # Auto-deduce language from dialect if dialect belongs to a specific language
        if self.dialect in ['english', 'english_us', 'english_uk', 'english_aus', 'english_ind']:
            self.language = 'english'
        elif self.dialect in ['french_fr', 'french_ca']:
            self.language = 'french'
        elif self.dialect in ['spanish_es', 'spanish_latam']:
            self.language = 'spanish'
        elif self.dialect == 'german_de':
            self.language = 'german'
        elif self.dialect == 'italian_it':
            self.language = 'italian'
        elif self.dialect == 'turkish_tr':
            self.language = 'turkish'
        elif self.dialect == 'russian_ru':
            self.language = 'russian'
        elif self.dialect == 'urdu_pk':
            self.language = 'urdu'
        elif self.dialect == 'hindi_in':
            self.language = 'hindi'
        elif self.dialect == 'chinese_zh':
            self.language = 'chinese'
        elif not self.language:
            self.language = 'arabic'

        if self.is_active:
            # Ensure only one active profile per user
            AgentProfile.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "language_display": self.get_language_display(),
            "voice_name": self.voice_name,
            "gender": self.gender,
            "gender_display": self.get_gender_display(),
            "dialect": self.dialect,
            "dialect_display": self.get_dialect_display(),
            "persona_role": self.persona_role,
            "persona_role_display": self.persona_role,
            "speaking_style": self.speaking_style,
            "speaking_style_display": self.speaking_style,
            "verbosity": self.verbosity or "balanced",
            "verbosity_display": self.get_verbosity_display(),
            "custom_instructions": self.custom_instructions,
            "off_topic_response": self.off_topic_response or "",
            "custom_role_id": self.custom_role_id,
            "custom_role": self.custom_role.to_dict() if self.custom_role else None,
            "welcome_message": self.welcome_message or "",
            "is_welcome_message_enabled": self.is_welcome_message_enabled,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }


class TenantCustomRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_roles', verbose_name="المستخدم / المؤسسة")
    name = models.CharField(max_length=120, verbose_name="اسم الدور المخصص")
    industry = models.CharField(max_length=64, blank=True, default='custom', verbose_name="القطاع أو التصنيف")
    description = models.CharField(max_length=255, blank=True, default='', verbose_name="وصف مختصر للدور")
    role_prompt = models.TextField(verbose_name="نص البرومبت والتوجيه المخصص للشخصية")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")

    class Meta:
        db_table = 'voice_assistant_tenantcustomrole'
        ordering = ['-updated_at']
        unique_together = ('user', 'name')
        verbose_name = "دور ذكاء اصطناعي مخصص للمؤسسة"
        verbose_name_plural = "مكتبة الأدوار المخصصة للمؤسسات"

    def __str__(self):
        return f"[{self.user.username}] {self.name} ({self.industry})"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "industry": self.industry or "custom",
            "description": self.description or "",
            "role_prompt": self.role_prompt,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }


class UserMCPServer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mcp_servers')
    name = models.CharField(max_length=100, default='خادم أدوات خارجي (FastMCP)')
    server_url = models.CharField(max_length=500, blank=True, default='')
    auth_token = models.CharField(max_length=500, blank=True, default='')
    is_active = models.BooleanField(default=True)
    cached_tools = models.JSONField(default=list, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_usermcpserver'
        ordering = ['-updated_at']

    def __str__(self):
        status = " [نشط]" if self.is_active else " [معطل]"
        return f"{self.name} ({self.server_url}){status}"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "server_url": self.server_url,
            "auth_token": self.auth_token,
            "is_active": self.is_active,
            "cached_tools": self.cached_tools or [],
            "tools_count": len(self.cached_tools or []),
            "last_synced_at": self.last_synced_at.strftime("%Y-%m-%d %H:%M") if self.last_synced_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


class SystemSetting(models.Model):
    gemini_api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Google Gemini API Key",
        help_text="المفتاح المركزي لخدمات Google Gemini Live ونظام الـ RAG الصوتي"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voice_assistant_systemsetting'
        verbose_name = "إعدادات النظام العامة"
        verbose_name_plural = "إعدادات النظام العامة"

    def __str__(self):
        status = "مُفعّل" if (self.gemini_api_key and self.gemini_api_key.strip()) else "غير محدد"
        return f"إعدادات النظام (Google Gemini API Key: {status})"

    @classmethod
    def get_settings(cls):
        setting, _ = cls.objects.get_or_create(id=1)
        return setting

    @classmethod
    def get_gemini_api_key(cls):
        setting = cls.objects.filter(id=1).first()
        if setting and setting.gemini_api_key and setting.gemini_api_key.strip():
            return setting.gemini_api_key.strip()
        from django.conf import settings
        return getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')


class AgentToolCallLog(models.Model):
    TOOL_TYPE_CHOICES = [
        ('mcp', 'خادم أدوات خارجي (FastMCP)'),
        ('rag', 'بحث المستندات (RAG)'),
        ('memory', 'ذاكرة العملاء (CRM Memory)'),
        ('transfer', 'تحويل طابور (Queue Transfer)'),
    ]

    STATUS_CHOICES = [
        ('success', 'ناجح (Success)'),
        ('failed', 'فشل أداة (Tool Error)'),
        ('timeout', 'انتهاء المهلة (Timeout)'),
        ('connection_error', 'فشل اتصال (Connection Error)'),
        ('validation_error', 'خطأ تحقق (Validation Error)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_tool_call_logs', verbose_name="العميل / الشركة")
    call_session = models.ForeignKey('crm.CallSession', on_delete=models.SET_NULL, null=True, blank=True, related_name='tool_call_logs', verbose_name="جلسة المكالمة")
    room_name = models.CharField(max_length=120, db_index=True, verbose_name="معرف الغرفة")
    caller_phone = models.CharField(max_length=64, blank=True, default='', verbose_name="رقم المتصل")
    tool_name = models.CharField(max_length=100, db_index=True, verbose_name="اسم الأداة")
    tool_type = models.CharField(max_length=30, choices=TOOL_TYPE_CHOICES, default='mcp', verbose_name="نوع الأداة")
    server_name = models.CharField(max_length=150, blank=True, default='', verbose_name="اسم السيرفر / النظام")
    server_url = models.CharField(max_length=500, blank=True, default='', verbose_name="رابط الخادم")
    arguments = models.JSONField(default=dict, blank=True, verbose_name="مدخلات الأداة (Arguments)")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='success', db_index=True, verbose_name="حالة التنفيذ")
    error_type = models.CharField(max_length=50, blank=True, default='none', verbose_name="نوع الخطأ")
    error_message = models.TextField(blank=True, default='', verbose_name="سبب ورسالة الخطأ")
    response_preview = models.TextField(blank=True, default='', verbose_name="معاينة الرد")
    raw_response = models.JSONField(null=True, blank=True, default=dict, verbose_name="الرد الكامل (JSON)")
    execution_time_ms = models.IntegerField(default=0, verbose_name="مدة التنفيذ (ms)")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="وقت الاستدعاء")

    class Meta:
        db_table = 'voice_assistant_agenttoolcalllog'
        ordering = ['-created_at']
        verbose_name = "سجل استدعاء الأداة"
        verbose_name_plural = "مراقبة استدعاءات الأدوات (Tool Logs)"

    def __str__(self):
        status_label = self.get_status_display()
        return f"{self.tool_name} [{status_label}] - {self.room_name} ({self.execution_time_ms}ms)"


class TenantLiveContext(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='live_context', verbose_name="العميل / الشركة")
    data = models.JSONField(default=dict, blank=True, verbose_name="البيانات المنظمة اللحظية (Structured JSON)")
    size_bytes = models.IntegerField(default=0, verbose_name="حجم البيانات (بايت)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, db_index=True, verbose_name="آخر تحديث")

    class Meta:
        db_table = 'voice_assistant_tenantlivecontext'
        verbose_name = "الذاكرة المنظمة الحية (Live Context)"
        verbose_name_plural = "الذاكرة المنظمة الحية (Live Contexts)"

    def __str__(self):
        return f"Live Context: {self.user.username} ({self.size_bytes} bytes)"

    def save(self, *args, **kwargs):
        import json
        if self.data is not None:
            try:
                self.size_bytes = len(json.dumps(self.data, ensure_ascii=False).encode('utf-8'))
            except Exception:
                self.size_bytes = 0
        else:
            self.data = {}
            self.size_bytes = 0
        super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "data": self.data or {},
            "size_bytes": self.size_bytes,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }



