import os, sys, psycopg2
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from knowledge.models import Document, DocumentChunk

doc = Document.objects.filter(id=77).first()
if not doc:
    print("Doc 77 not found!")
    sys.exit(1)

chunks = list(doc.chunks.order_by('chunk_index'))
full_content = "\n\n".join([c.content for c in chunks])
print(f"Loaded Doc 77 '{doc.title}': {len(chunks)} chunks, {len(full_content)} chars")

conn = psycopg2.connect(
    dbname="chatwoot_production",
    user="postgres",
    password="ChatwootDbPassword2026",
    host="omni_postgres",
    port=5432
)
cur = conn.cursor()

cur.execute("SELECT id, name FROM captain_documents WHERE name = %s AND assistant_id = 1", (doc.title,))
existing = cur.fetchone()

if existing:
    doc_id = existing[0]
    print(f"Updating existing Chatwoot captain_document #{doc_id}")
    cur.execute("""
        UPDATE captain_documents
        SET content = %s, status = 1, sync_status = 1, updated_at = NOW(),
            metadata = %s
        WHERE id = %s
    """, (full_content, '{"source": "django_rag_sync", "doc_id": 77}', doc_id))
else:
    print("Inserting new Chatwoot captain_document for كورا.txt")
    cur.execute("""
        INSERT INTO captain_documents (
            assistant_id, account_id, name, external_link, content, status, sync_status,
            metadata, created_at, updated_at
        ) VALUES (
            1, 2, %s, %s, %s, 1, 1,
            %s, NOW(), NOW()
        ) RETURNING id
    """, (doc.title, f"MARKDOWN: kura_restaurant_guide_{doc.id}.md", full_content, '{"source": "django_rag_sync", "doc_id": 77}'))
    doc_id = cur.fetchone()[0]

print(f"Chatwoot Document ID: {doc_id}")

cur.execute("DELETE FROM captain_assistant_responses WHERE documentable_id = %s AND documentable_type = 'Captain::Document'", (doc_id,))

responses_data = [
    (
        "ما هي الميزات التشغيلية والتجارية لمنظومة كورا لإدارة المطاعم؟",
        full_content[:2500]
    ),
    (
        "ما هي مميزات موظف الكول سنتر الذكي بالذكاء الاصطناعي (AI Voice Call Center) في منظومة كورا؟",
        """موظف الكول سنتر الذكي في كورا يعمل 24/7 ويقدم:
- استقبال فوري للمكالمات دون انتظار والقضاء على انشغال الخطوط في الذروة.
- التحدث بلهجة العميل: دعم اللهجات (المصرية، السعودية، الإماراتية، الكويتية، والفصحى) بلباقة.
- إلمام كامل بالمنيو والأسعار والعروض مع فحص فوري للمكونات والبدائل ومسببات الحساسية.
- التعرف التلقائي على العميل وعناوينه السابقة وتفضيلاته فور اتصاله.
- فحص تغطية التوصيل والكومبوندات وحساب رسوم ووقت التوصيل التقديري.
- إرسال الطلب للمطبخ مباشرة وحساب الفاتورة الإجمالية شاملة الضريبة.
- تتبع وإلغاء الطلبات هاتفياً وتحليلات تسجيل وتفريغ المكالمات."""
    ),
    (
        "ما هي مواصفات نقطة البيع ونظام الكاشير السريع (Smart POS) في منظومة كورا؟",
        """نقطة البيع Smart POS في منظومة كورا تتميز بـ:
- دعم كافة قنوات البيع: صالة (Dine-in)، سفري (Takeaway)، وتوصيل (Delivery).
- سرعة تسجيل الأوردرات بواجهة لمسية متطورة وسريعة جداً.
- تعديلات الأصناف الذكية (Modifiers/Notes): إضافة صوص، بدون بصل، حجم كبير، مع حساب الفروق السعرية آلياً.
- طرق دفع مرنة متعددة: نقدي، بطاقة ائتمان، محافظ إلكترونية، ودمج طرق الدفع في فاتورة واحدة.
- العمل دون إنترنت (Offline Mode) ومزامنة الفواتير فور عودة الاتصال لمنع توقف الكاشير."""
    ),
    (
        "كيف تعمل شاشات عرض المطبخ الذكية (KDS) في كورا وتستغني عن البون الورقي؟",
        """شاشات المطبخ الذكية (KDS) في منظومة كورا:
- استغناء تام عن البون الورقي ومشاكل ضياع أو تلف البونات.
- عرض الأوردرات في لحظة تسجيلها من الكاشير أو الكول سنتر أو الأونلاين مصنفة بالألوان حسب وقت الانتظار.
- توجيه الأصناف تلقائياً لمحطات الطهي المحددة (شاشة المشويات، شاشة البرجر، شاشة التجهيز والتغليف).
- تنبيهات فورية للمطبخ عند نفاد أي مادة خام لإيقاف بيع الصنف (Out-of-Stock)."""
    ),
    (
        "كيف تتم إدارة الطاولات والحجوزات (Dine-in & Table Management) في كورا؟",
        """إدارة الطاولات والحجوزات في كورا تشمل:
- خريطة تفاعلية لصالة المطعم توضح حالة كل طاولة (شاغرة، مشغولة، قيد التنظيف، محجوزة).
- دمج ونقل الفواتير بين الطاولات بسلاسة عند انتقال الضيوف.
- تقسيم الشيك (Split Bill) بكل مرونة بحسب الأصناف أو بالتساوي بين الأفراد.
- طلب ذاتي عبر الـ QR Code من الطاولة مباشرة مع الدفع الإلكتروني."""
    ),
    (
        "ما هي مميزات إدارة المخزون وتكاليف الوصفات (Inventory & Recipe Costing) في كورا؟",
        """إدارة المخزون والتكاليف في منظومة كورا:
- الخصم الآلي للمكونات الخام بناءً على الوصفات (Recipe Depletion) مع كل صنف مباع.
- تتبع دقيق للهدر والفاقد وتالف المطبخ لمعرفة أسبابه وتحديد المسؤوليات.
- جرد دوري سريع ومقارنة الكميات الفعلية مع المسجلة بالنظام لكشف العجز أو السرقات.
- تنبيهات الوصول للحد الأدنى من المخزون وتوليد أوامر شراء آلية للموردين."""
    ),
    (
        "ما هي تحليلات وتقارير الأعمال (BI & Sales Analytics) التي توفرها كورا؟",
        """لوحات التحليلات والبيانات في كورا تقدم:
- تقارير مبيعات لحظية ومؤشرات الأداء الرئيسية (KPIs) من الهاتف أو المتصفح.
- تحليل مصفوفة هندسة المنيو (Menu Engineering): تحديد الأصناف الأكثر ربحية وشعبية (Stars, Puzzles, Plowhorses, Dogs).
- تحليل أداء قنوات البيع ونسب المبيعات بين الصالة والسفري والتوصيل والكول سنتر.
- تحليل أداء الفروع ومقارنة إيراداتها ومتوسط الفاتورة لكل فرع."""
    ),
    (
        "كيف تدعم منظومة كورا الفاتورة الإلكترونية والربط الضريبي والامتثال؟",
        """الامتثال الضريبي في منظومة كورا:
- توافق كامل ومباشر مع متطلبات الفاتورة الإلكترونية (ZATCA في السعودية ومصلحة الضرائب المصرية).
- إصدار فواتير ضريبية مبسطة تحتوي على الـ QR Code المشفر والمختوم رقمياً فور إغلاق الحساب.
- ربط سحابي فوري ومباشر مع منصات الضرائب دون الحاجة لأجهزة وسيطة معقدة."""
    )
]

for idx, chunk in enumerate(chunks):
    q = f"تفاصيل ومعلومات كورا - جزء {idx+1}:"
    responses_data.append((q, chunk.content))

for question, answer in responses_data:
    cur.execute("""
        INSERT INTO captain_assistant_responses (
            assistant_id, account_id, question, answer, status,
            documentable_type, documentable_id, edited, created_at, updated_at
        ) VALUES (
            1, 2, %s, %s, 1,
            'Captain::Document', %s, false, NOW(), NOW()
        )
    """, (question, answer, doc_id))

conn.commit()
print(f"Successfully inserted {len(responses_data)} Q&A responses into Chatwoot Captain AI!")

cur.execute("SELECT COUNT(*) FROM captain_assistant_responses WHERE documentable_id = %s", (doc_id,))
count = cur.fetchone()[0]
print(f"Verified count in captain_assistant_responses: {count}")

conn.close()
