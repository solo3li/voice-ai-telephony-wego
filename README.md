# Voice AI & Telephony Platform (Wazo + LiveKit AI)

منظومة موحدة تجمع بين بدالة الاتصالات السحابية (**Wazo Platform / Asterisk**) ومحرك الذكاء الاصطناعي الصوتي التفاعلي (**LiveKit + Python Voice Agent**).

## هيكل المشروع (Project Structure)

```text
voice-ai-telephony/
├── wazo/                      # بيئة بدالة Wazo وإعدادات الميكروسيرفيس
│   ├── wazo-docker/           # docker-compose.yml وملفات تشغيل Wazo
│   └── repos/                 # مستودعات xivo-config و wazo-auth-keys
├── test-calll-ai/             # بيئة الذكاء الاصطناعي الصوتي LiveKit
│   ├── django_app/            # لوحة تحكم Django وإدارة الفوترة والـ APIs
│   ├── agent/                 # محرك الـ Voice Agent (STT + LLM + TTS)
│   ├── docker-compose.yml     # تشغيل LiveKit, SIP, Centrifugo, Inngest
│   └── ...
└── .gitignore                 # حماية ملفات البيئة والمفاتيح الحساسة
```

## المنافذ الأساسية (Port Allocations)

- **Wazo Web UI / Admin:** `https://<IP>:8443`
- **Wazo SIP (Asterisk):** `5070` (UDP / TCP)
- **Wazo RTP Audio Range:** `19980-20000/udp`
- **LiveKit SIP Gateway:** `5060` (UDP / TCP)
- **LiveKit SFU (WebRTC):** `7881` TCP / `7882` UDP / `50000-50020/udp`
- **Django APIs & Docs:** `https://app.<IP>.nip.io/api/v1/docs/`
