# 🤖 AI NEXUS PROXY v6.0 — ULTRA EDITION

<div align="center">

![Logo](logo.png)

**بوابة ذكية للوصول إلى نماذج الذكاء الاصطناعي المتقدمة**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Latest-red.svg)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 📋 نظرة عامة

**AI NEXUS PROXY v6.0** هو حل متقدم يوفر واجهة برمجية موحدة للوصول إلى مجموعة واسعة من نماذج الذكاء الاصطناعي من مزودين مختلفين، مع ميزات أمان وأداء متطورة.

### ✨ المميزات الرئيسية

- **⚡ بنية متطورة**: Asyncio + Playwright + FastAPI + Pydantic v2
- **🛡️ أمان متكامل**: مصادقة API Key + تعقيم المدخلات + العزل الآمن
- **🎯 أداء عالي**: تخزين مؤقت LRU-TTL | تحديد المعدن | مجمع الجلسات | طابور المهام
- **🔒 خفي**: حماية من البصمة الرقمية (Canvas/Font/WebRTC) + مكافحة الكشف
- **🔄 مرونة**: قاطع الدائرة | إعادة المحاولة الأسية | الاسترداد التلقائي
- **📡 وقت حقيقي**: بث WebSocket | SSE | معالجة مجمعة

---

## 🚀 المزودون المدعومون

### DuckDuckGo AI Chat
- GPT-4o
- Claude-3-Haiku
- Llama-3
- Mixtral
- Gemini

### LMSYS Chatbot Arena
- Claude-3-Opus
- Claude-Sonnet-3.5
- Gemini-Pro
- Qwen2
- والمزيد...

---

## 🔥 ميزات الإصدار 6.0 الجديدة

| الميزة | الوصف |
|--------|-------|
| ⚡ نمط قاطع الدائرة | حماية لكل مزود من الفشل المتتالي |
| 📊 طابور الطلبات | أولوية ومجمع عمال قابل للتكوين |
| 🔄 بث مباشر | نقاط نهاية WebSocket و SSE |
| 🔐 مصادقة API | دعم Bearer Token و Header |
| 🌐 تدوير البروكسي | تدوير ذكي مع فحص الصحة |
| 📸 لقظات الفشل | تسجيل HAR ولقطات شاشة تلقائية |
| 💾 مراقب الذاكرة | إعادة تشغيل تلقائي عند استهلاك الذاكرة |
| 📦 معالجة مجمعة | نقطة نهاية `/batch` للمعالجة غير المتزامنة |
| 🎭 إخفاء متقدم | Canvas/Font/WebRTC Stealth |
| 🛑 إيقاف أنيق | تصريف الطلبات قبل الإغلاق |

---

## 📦 التثبيت

### المتطلبات الأساسية

```bash
Python 3.8+
pip
```

### تثبيت التبعيات

```bash
pip install -r requirements.txt
```

### تثبيت Playwright

```bash
playwright install
```

---

## 🚀 التشغيل

### بدء الخادم

```bash
python main.py
```

### تحديد المنفذ

```bash
python main.py --port 8000
```

---

## 📖 استخدام الـ API

### المصادقة

```bash
# باستخدام Bearer Token
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/v1/chat/completions

# باستخدام Header
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/v1/chat/completions
```

### مثال على طلب محادثة

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "مرحباً، كيف يمكنني مساعدتك؟"}
    ]
  }'
```

### المعالجة المجمعة

```bash
curl -X POST http://localhost:8000/v1/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "requests": [
      {"model": "gpt-4o", "messages": [{"role": "user", "content": "السؤال الأول"}]},
      {"model": "claude-3", "messages": [{"role": "user", "content": "السؤال الثاني"}]}
    ]
  }'
```

---

## 🔧 التكوين

### متغيرات البيئة

```bash
# مفتاح API للمصادقة
API_KEY=your_secret_key_here

# منفذ الخادم
PORT=8000

# إعدادات الذاكرة
MEMORY_THRESHOLD=90

# إعدادات البروكسي
PROXY_ENABLED=true
PROXY_LIST=path/to/proxies.txt
```

---

## 📊 المراقبة

### Prometheus Metrics

```bash
curl http://localhost:8000/metrics
```

### سجلات HAR

يتم حفظ سجلات HAR تلقائياً عند الفشل في:
```
./har_logs/
```

---

## 🗂️ هيكل المشروع

```
├── main.py                 # الملف الرئيسي للتطبيق
├── index.html             # واجهة المستخدم
├── logo.png               # شعار المشروع
├── .gitignore            # ملفات Git المتجاهلة
├── AimAssistPro_Linux/   # حزمة Linux
│   ├── AimAssistPro_Linux.zip
│   ├── AimAssistPro_Windows.zip
│   └── extracted_linux/
└── README.md             # هذا الملف
```

---

## 🔒 الأمان

### أفضل الممارسات

1. **لا تشارك مفاتيح API** مع أي شخص
2. **استخدم HTTPS** في بيئة الإنتاج
3. **حدّ من معدل الطلبات** لمنع إساءة الاستخدام
4. **راقب السجلات** بانتظام لاكتشاف الأنشطة المشبوهة
5. **حدّث التبعيات** بانتظام

---

## 🤝 المساهمة

نرحب بالمساهمات! يرجى اتباع الخطوات التالية:

1. Fork المشروع
2. إنشاء فرع للميزة (`git checkout -b feature/AmazingFeature`)
3. Commit التغييرات (`git commit -m 'Add some AmazingFeature'`)
4. Push للفرع (`git push origin feature/AmazingFeature`)
5. فتح Pull Request

---

## 📄 الترخيص

هذا المشروع مرخص بموجب ترخيص MIT - راجع ملف [LICENSE](LICENSE) للتفاصيل.

---

## 📞 الدعم

للأسئلة والمشاكل:

- 📧 افتح Issue في GitHub
- 💬 انضم إلى قناة المناقشة
- 📖 راجع الوثائق الكاملة

---

## 🙏 شكر وتقدير

- **FastAPI** - لإطار العمل السريع
- **Playwright** - لأتمتة المتصفح
- **المجتمع المفتوح المصدر** - للأدوات والمكتبات الرائعة

---

<div align="center">

**صنع بحب ❤️ بواسطة فريق AI NEXUS**

⭐ إذا أعجبك المشروع، لا تنسَ إعطاءه نجمة!

</div>
