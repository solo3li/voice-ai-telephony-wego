# Voice AI Telephony & Omnichannel Platform (Wazo + LiveKit + B2B Partner SaaS)

منظومة اتصالات سحابية وذكاء اصطناعي صوتي فائق السرعة تجمع بين بدالة الاتصالات الرقمية (**Wazo Platform / Asterisk**) ومحرك المعالجة الصوتية اللحظية (**LiveKit WebRTC + Python Voice Agents**) مع واجهات برمجية كاملة للشركاء والمطورين (**Headless B2B SaaS & Developer APIs**).

---

## 🏛️ نظرة عامة على المعمارية (System Architecture)

```text
                               ┌────────────────────────────────────────────────────────┐
                               │            Inbound & Outbound Telephony                │
                               │   PSTN / SIP Trunks (Twilio, Zadarma, Local Telcos)    │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
                                   ┌───────────────────────┴───────────────────────┐
                                   │                                               │
                                   ▼ SIP: 5070                                     ▼ SIP: 5060
                  ┌─────────────────────────────────┐             ┌─────────────────────────────────┐
                  │    Wazo Platform / Asterisk     │             │       LiveKit SIP Gateway       │
                  │   PBX Queues, Human Extensions, │             │    Direct WebRTC Media Bridge   │
                  │       IVR & Call Transfers      │             └────────────────┬────────────────┘
                  └────────────────┬────────────────┘                              │
                                   │                                               │
                                   │                                               ▼ WebRTC: 7880/7881
                                   │                              ┌─────────────────────────────────┐
                                   │                              │          LiveKit SFU            │
                                   │                              └────────────────┬────────────────┘
                                   │                                               │
                                   └───────────────────────┬───────────────────────┘
                                                           │ Audio RTP / WebRTC Frames
                                                           ▼
                                  ┌──────────────────────────────────────────────────┐
                                  │           Python LiveKit Voice Agent             │
                                  │  • STT: Deepgram Nova-2 (Arabic & English)       │
                                  │  • LLM: Gemini 2.0 / 2.5 Flash (Low Latency)     │
                                  │  • TTS: Cartesia Sonic / ElevenLabs / Kokoro     │
                                  │  • VAD: Silero Turn-taking & Interruption        │
                                  │  • FastMCP Client (Real-time Tool Calling)       │
                                  └────────────────────────┬─────────────────────────┘
                                                           │
                                           ┌───────────────┴───────────────┐
                                           ▼                               ▼
                      ┌─────────────────────────────────┐         ┌─────────────────────────────────┐
                      │    Redis Structured Context     │         │      FastMCP External Tools     │
                      │  Live Working Memory (< 2ms)    │         │  SaaS Tools via SSE (Orders,    │
                      │   (Menu, Branches, Real-time)   │         │    Delivery, POS, CRM Lookups)  │
                      └─────────────────────────────────┘         └─────────────────────────────────┘
                                                           ▲
                                                           │
                               ┌───────────────────────────┴────────────────────────────┐
                               │               Django Core Platform API                 │
                               │  • Developer API (/api/v1/)                            │
                               │  • Headless SaaS Partner API (/api/partner/v1/)        │
                               │  • Pooled Multi-tenant Wallets & Minute Rounding       │
                               │  • Inngest Outbound Calling Campaign Scheduler         │
                               │  • Do Not Call (DNC) Compliance Engine                 │
                               │  • WhatsApp Omnichannel Bridge (Evolution API/Baileys) │
                               └────────────────────────────────────────────────────────┘
```

---

## 📚 التوثيق التفاعلي للـ APIs (Interactive API Documentation)

المنظومة مزودة بمحرك توثيق تفاعلي ثنائي اللغة (**عربي / إنجليزي**) مبني على تقنية **Scalar** ومحدث بنسبة 100% ليغطي جميع المسارات البرمجية:

### 1. واجهة المطورين المباشرة (Direct Developer API)
- **بوابة التوثيق التفاعلية (Scalar Docs):**  
  `https://app.<DOMAIN>/api/v1/docs/`
- **مواصفة OpenAPI 3.1 JSON المحدثة:**  
  `https://app.<DOMAIN>/api/v1/docs/openapi.json?lang=ar` (عربي)  
  `https://app.<DOMAIN>/api/v1/docs/openapi.json?lang=en` (English)
- **المصادقة:** عبر هيدر `X-API-Key: sk_live_usr_...` أو `Authorization: Bearer sk_live_usr_...`
- **الحزم البرمجية المشمولة (15 وسماً / 60 مساراً):**
  1. الحساب والمحفظة الشخصية (Account & Balance)
  2. البروفايلات الصوتية واللهجات (Voice Personas & Dialects)
  3. كتالوج الأدوار الوظيفية والصناعية (Industry AI Roles & Custom Library)
  4. ذاكرة العملاء وسجل السياق CRM (Customer Memory & CRM)
  5. قواعد المعرفة والبحث الدلالي (Semantic RAG & pgvector)
  6. خوادم وأدوات FastMCP الحية (FastMCP SSE Servers & Live Tools)
  7. خطوط السنترال وأرقام الهاتف (PBX Trunks & DIDs)
  8. دليل الموظفين والتحويلات الداخلية (Employee Directory & Extensions)
  9. طوابير الانتظار الكول سنتر (Call Queues & Routing)
  10. حملات الاتصال الآلي الصادرة (Outbound Campaigns via Inngest)
  11. قائمة منع الاتصال (Do Not Call - DNC Compliance)
  12. قنوات الواتساب والمراسلة التفاعلية (WhatsApp Omnichannel)
  13. سجلات المكالمات والفوترة اللحظية (CDR & Minute Billing)
  14. إشعارات الويبهوك الموقعة (Webhooks & HMAC Signatures)
  15. الذاكرة اللحظية المنظمة للنشاط (Structured Live Context in Redis)

### 2. واجهة الشركاء ومزودي الـ SaaS (Headless B2B Partner API)
- **بوابة التوثيق التفاعلية (Scalar Docs):**  
  `https://app.<DOMAIN>/api/partner/v1/docs/`
- **مواصفة OpenAPI 3.1 JSON المحدثة:**  
  `https://app.<DOMAIN>/api/partner/v1/docs/openapi.json?lang=ar` (عربي)  
  `https://app.<DOMAIN>/api/partner/v1/docs/openapi.json?lang=en` (English)
- **المصادقة:** عبر هيدر `X-Partner-Key: sk_live_prt_...`
- **الحزم البرمجية المشمولة (16 وسماً / 64 مساراً):**
  1. المحفظة المركزية الموحدة والفوترة بالجملة (Pooled Partner Wallet & Wholesale Rates)
  2. تسجيل وإدارة المتاجر والعملاء الفرعيين (Sub-client Provisioning & Spending Caps)
  3. بروفايلات وشخصيات عملاء الشريك (Client Personas & Dialects)
  4. الأدوار الوظيفية والصناعية لعملاء الشريك (Client AI Industry Roles)
  5. ذاكرة وبطاقات عملاء المتاجر CRM (Client Customer Memory)
  6. قواعد المعرفة لعملاء الشريك (Client RAG & Knowledge Base)
  7. خطوط السنترال وخطوط SIP للعميل (Client Telephony & DIDs)
  8. موظفو التحويل البشري للعميل (Client Staff Directory & Softphones)
  9. طوابير الانتظار لعملاء الشريك (Client Call Queues)
  10. حملات الاتصال الصادرة لعملاء الشريك (Client Outbound Campaigns)
  11. قائمة منع الاتصال للعميل (Client Do Not Call - DNC Registry)
  12. قنوات الواتساب والمراسلة للعملاء (Client WhatsApp Omnichannel)
  13. إدارة خوادم FastMCP لكل متجر (Client FastMCP Integration)
  14. سجلات مكالمات العملاء والتحليلات (Client CDR & Audio Recordings)
  15. ويبهوك إشعارات الشريك بتوقيع مشفر (Partner Webhooks & HMAC-SHA256)
  16. الذاكرة المنظمة الحية لمتجر العميل (Client Structured Live Context)

---

## 🔌 جدول المنافذ والشبكة (Port Allocations)

| الخدمة | المنفذ | البروتوكول | الاستخدام |
|---|:---:|:---:|---|
| **Traefik Reverse Proxy** | `80` / `443` | TCP | توجيه الدومينات وتوليد شهادات SSL/TLS تلقائياً |
| **Django Backend** | `8000` | TCP | واجهات الـ REST API وبوابات الإدارة والتوثيق |
| **LiveKit SFU Server** | `7880` / `7881` | TCP | خادم تدفق WebRTC وإشارات التحكم بالصوت |
| **LiveKit WebRTC Media** | `50000-50020` | UDP | حزم الصوت اللحظية للذكاء الاصطناعي |
| **LiveKit SIP Gateway** | `5060` | UDP / TCP | استقبال وتحويل مكالمات SIP للذكاء الاصطناعي |
| **Wazo Asterisk PBX** | `5070` | UDP / TCP | بدالة الاتصالات والموظفين والتحويلات الداخلية |
| **Wazo RTP Audio Range** | `19980-20000` | UDP | حزم الصوت الخاصة ببدالة Asterisk |
| **Wazo Admin UI / Nginx** | `8443` | TCP | لوحة إدارة بدالة Wazo وتهيئة التراخيص |
| **Redis Cache & Working Memory** | `6379` | TCP | كاش الذاكرة اللحظية Live Context وطوابير المهام |
| **PostgreSQL Database** | `5432` | TCP | قاعدة البيانات المركزية مع ملحق المتجهات `pgvector` |
| **Evolution API (WhatsApp)** | `8080` | TCP | محرك Baileys للربط مع شبكة واتساب وتوليد الـ QR |
| **Inngest Workflow Engine** | `8288` | TCP | جدولة ومزامنة الحملات الصادرة المتوازية |
| **MinIO Storage** | `9000` / `9001` | TCP | تخزين ملفات التسجيلات الصوتية والمستندات |
| **Prometheus & Grafana** | `9090` / `3000` | TCP | مراقبة أداء الخادم والأحمال المتزامنة |

---

## 🚀 دليل الشركاء للربط السريع (Partner Integration Quickstart)

### 1. استدعاء رصيد المحفظة المركزية
```bash
curl -X GET "https://app.<DOMAIN>/api/partner/v1/wallet/" \
  -H "X-Partner-Key: sk_live_prt_your_key_here"
```

### 2. تسجيل متجر / عميل فرعي وضبط السقف المالي
```bash
curl -X POST "https://app.<DOMAIN>/api/partner/v1/clients/register/" \
  -H "X-Partner-Key: sk_live_prt_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "مطعم بيتزا نابولي",
    "external_reference": "tenant_napoli_101",
    "spending_cap": 30.0,
    "minute_cap": 400
  }'
```

### 3. ربط خادم أدوات المطعم (FastMCP SSE Server)
```bash
curl -X POST "https://app.<DOMAIN>/api/partner/v1/clients/{client_id}/mcp/" \
  -H "X-Partner-Key: sk_live_prt_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "خادم أدوات بيتزا نابولي",
    "server_url": "https://napoli.com/sse?access_key=ak_napoli_secret",
    "sync_now": true
  }'
```

### 4. حقن بيانات المنيو والفروع في كاش الذاكرة اللحظية (Redis)
```bash
curl -X PUT "https://app.<DOMAIN>/api/partner/v1/clients/{client_id}/context/" \
  -H "X-Partner-Key: sk_live_prt_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "restaurant_name": "بيتزا نابولي",
    "menu": {
      "بيتزا": [{"name": "مارجريتا", "price": 45}],
      "مشروبات": [{"name": "بيبسي", "price": 5}]
    },
    "branches": [{"name": "فرع التحلية", "status": "مفتوح"}],
    "out_of_stock": []
  }'
```

### 5. إطلاق مكالمة صوتية ذكية صادرة للعميل (Outbound AI Dial)
```bash
curl -X POST "https://app.<DOMAIN>/api/partner/v1/clients/{client_id}/calls/dial/" \
  -H "X-Partner-Key: sk_live_prt_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+966501234567",
    "customer_name": "أحمد السعيد",
    "call_goal": "تأكيد طلب التوصيل رقم 5501 وتحديد وقت الاستلام"
  }'
```

---

## 🛠️ إدارة وتشغيل المنظومة (Operations & Maintenance)

### تشغيل حاويات المشروع:
```bash
cd /root/voice-ai-telephony/test-calll-ai
docker compose up -d
```

### إعادة تشغيل حاوية تطبيق Django:
```bash
docker restart voice_django
```

### فحص سجلات محرك الصوت التفاعلي LiveKit Agent:
```bash
docker logs voice_agent -f --tail 50
```

### فحص مطابقة التوثيق للأكواد الحية:
```bash
docker exec voice_django python -c "
from developer.user_openapi_spec import get_user_openapi_spec
from partners.openapi_spec import get_partner_openapi_spec
print('Dev endpoints:', len(get_user_openapi_spec()['paths']))
print('Partner endpoints:', len(get_partner_openapi_spec()['paths']))
"
```
*(النتيجة المتوقعة: 60 مساراً للمطورين و 64 مساراً للشركاء بتغطية كاملة 100%).*
