# 📶 WiFi Shop Manager (مدير واي فاي المحل التجاري)

<p align="center">
  <img src="src/assets/logo.png" alt="WiFi Shop Manager Logo" width="120" onerror="this.style.display='none'"/>
  <br>
  <b>أداة سطح مكتب ذكية واحترافية لنظام Windows لإدارة شبكة واي فاي المحلات التجارية وتوليد قسائم إنترنت مؤقتة للزبائن.</b>
  <br>
  <i>A modern Windows desktop tool to manage shop Wi-Fi hotspots, generate temporary voucher access codes, and monitor connected customers.</i>
</p>

<p align="center">
  <a href="#features">المميزات</a> •
  <a href="#repo-structure">هيكل المشروع</a> •
  <a href="#installation">التثبيت والتشغيل</a> •
  <a href="#building-exe">بناء ملف EXE</a> •
  <a href="#github-releases">التوزيع عبر GitHub Releases</a> •
  <a href="#license">الترخيص</a>
</p>

---

## 🌟 نظرة عامة عن المشروع (Overview)

تم تصميم **WiFi Shop Manager** خصيصاً لأصحاب المحلات التجارية، المقاهي، وصالونات الانتظار الذين يرغبون في تقديم خدمة إنترنت مؤقتة لزبائنهم عبر جهاز الكمبيوتر المحمول أو المكتبي المزود بقطعة واي فاي (Wi-Fi Adapter)، دون الحاجة لشراء راوترات احترافية باهظة الثمن أو اشتراكات معقدة.

يقوم البرنامج بـ:
1. تحويل بطاقة الواي فاي في حاسوبك إلى نقطة بث (Hotspot).
2. تشغيل بوابة تسجيل دخول خفيفة (Captive Portal) يفتحها الزبون على هاتفه.
3. توليد قسائم دخول (Vouchers) برمز مؤقت ورمز استجابة سريعة (QR Code) مع تحديد مدة الصلاحية (مثلاً: 30 دقيقة، ساعة، ساعتان).
4. قطع الاتصال تلقائياً فور انتهاء مدة صلاحية الكود.

---

<a name="features"></a>
## ✨ المميزات الرئيسية (Key Features)

- **⚡ التكوين التلقائي ومشاركة الإنترنت بدون تدخل (Zero-Touch Auto-Config & ICS) [ميزة استثنائية]:**
  - بمجرد توصيل قطعة الواي فاي (Clé Wi-Fi) بمنفذ USB وتشغيل البرنامج، يقوم النظام برمجياً في الخلفية بفحص القطعة وتفعيل وضع نقطة البث.
  - يقوم بضبط وتفعيل ميزة مشاركة الإنترنت (Windows Internet Connection Sharing - ICS) تلقائياً عبر واجهة برمجة COM (`HNetCfg.HNetShare`)، ليتم تمرير الإنترنت للأجهزة المتصلة فوراً **دون الحاجة لأي ضبط يدوي في لوحة تحكم ويندوز**.
  - مراقبة حية لمنفذ USB (Plug & Play Daemon): إذا تم فصل القطعة يتوقف البث مؤقتاً، وبمجرد إعادة توصيلها يستأنف البث وتفعيل مشاركة الإنترنت تلقائياً.
- **⚡ تحكم كامل في نقطة البث (Hotspot Controller):** تشغيل وإيقاف نقطة بث الواي فاي في ويندوز 10 و 11 بنقرة زر واحدة مع إمكانية تخصيص اسم الشبكة (SSID) وكلمة المرور.
- **🖼️ كود QR ثابت للحائط (Static Wall Poster) [ميزة استثنائية]:**
  - لا داعي لطباعة قسائم ورقية مستمرة يومياً! اطبع ملصقاً واحداً عالي الجودة وعلّقه على الحائط أو الطاولات.
  - بمجرد مسح الزبون للكود بكاميرا هاتفه، تفتح له البوابة الترحيبية تلقائياً.
- **🚀 توليد حساب فريد ومؤقت ذاتياً (Self-Service On-Demand Credentials):**
  - عندما يضغط الزبون على "بدء الاتصال"، يولد له البرنامج فوراً **اسم مستخدم ورمز دخول فريد ومؤقت خاص بجهازه وحده** (مثل: `GUEST-8294` / `8294`).
  - إذا مسح زبون آخر نفس الكود الثابت، يحصل على اسم مستخدم وكود مختلف تماماً!
  - تبدأ صلاحية كل زبون بالعد التنازلي وتنتهي تلقائياً فور نفاد المدة المحددة (مثلاً 60 دقيقة).
- **🎟️ توليد قسائم يدوية مخصصة (Custom Vouchers):** إمكانية إصدار قسائم مدفوعة أو لمدد مخصصة (طاولات VIP).
- **📱 بوابة تسجيل دخول محلية (Local Captive Portal):** صفحة ويب ترحيبية أنيقة متجاوبة مع الهواتف الذكية تعمل محلياً بدون الحاجة لإنترنت خارجي لتشغيلها.
- **⏱️ مراقبة الصلاحية والانتهاء التلقائي (Auto-Expiry Engine):** محرك فحص دوري يقوم بمراجعة الجلسات النشطة وإلغاء صلاحية الوصول للأجهزة التي نفد وقتها.
- **👥 شاشة مراقبة الأجهزة المتصلة (Live Connected Clients):** عرض قائمة الأجهزة المتصلة حالياً مع عناوين الـ IP و MAC واسم الجهاز والوقت المتبقي، مع زر طرد/حظر فوري.
- **🎨 واجهة مستخدم رسومية حديثة (Modern UI):** مبنية بأحدث تقنيات `CustomTkinter` وتدعم النمطين الليلي والفاتح (Dark/Light Mode).
- **🚀 أتمتة البناء والنشر (CI/CD Automated Builds):** ملف إعداد جاهز لـ **GitHub Actions** يتيح تجميع الأكواد تلقائياً إلى ملف تنفيذي مستقل (`.exe`) عند كل تحديث ورفعه في صفحة Releases.

---

<a name="repo-structure"></a>
## 📂 هيكل مجلدات المشروع (Repository Structure)

```text
wifi-shop-manager/
├── .github/
│   └── workflows/
│       └── release.yml          # مسار عمل GitHub Actions لبناء الـ EXE تلقائياً عند إطلاق إصدار جديد
├── src/
│   ├── core/                    # اللبنات البرمجية الأساسية للنظام
│   │   ├── __init__.py
│   │   ├── wifi_controller.py   # إدارة نقطة البث ومراقبة محول الشبكة (Netsh / Win32 API)
│   │   ├── voucher_manager.py   # منطق توليد وتتبع وإلغاء صلاحيات قسائم الدخول (قاعدة بيانات SQLite)
│   │   └── captive_server.py    # خادم البوابة الترحيبية للتحقق من الأكواد وتفعيل الجلسات
│   ├── gui/                     # واجهة المستخدم الرسومية (GUI)
│   │   ├── __init__.py
│   │   ├── main_window.py       # النافذة الرئيسية ولوحة التحكم
│   │   └── components/          # عناصر الواجهة الفرعية (بطاقات القسائم وجداول المتصلين)
│   │       ├── __init__.py
│   │       ├── voucher_card.py
│   │       └── client_table.py
│   ├── utils/                   # أدوات مساعدة
│   │   ├── __init__.py
│   │   ├── config.py            # إعدادات البرنامج والمسارات الافتراضية
│   │   └── qr_helper.py         # توليد وحفظ صور الـ QR Code
│   ├── assets/                  # أيقونات وملفات الواجهة الرسومية
│   └── main.py                  # نقطة الدخول الرئيسية للبرنامج
├── tests/                       # اختبارات الوحدة (Unit Tests)
│   └── test_vouchers.py
├── .gitignore                   # تجاهل الملفات المؤقتة والبيئات الافتراضية
├── build_exe.bat                # سكربت سطر أوامر محلي لويندوز لبناء ملف .exe بضغطة واحدة
├── requirements.txt             # المكتبات البرمجية المطلوبة
├── LICENSE                      # رخصة الاستخدام مفتوحة المصدر (MIT)
└── README.md                    # هذا الملف التوثيقي
```

---

<a name="installation"></a>
## 🛠️ التثبيت والتشغيل للمطورين (Development Setup)

### المتطلبات الأساسية:
- نظام تشغيل **Windows 10 أو Windows 11**.
- مهايئ واي فاي يدعم ميزة نقطة البث (Wi-Fi Adapter with Hosted Network / Mobile Hotspot support).
- تثبيت **Python 3.10** أو أحدث ([تحميل بايثون](https://www.python.org/downloads/)).
- **تشغيل موجه الأوامر كمسؤول (Run as Administrator)** لأن إدارة شبكات ويندوز ومهايئات الشبكة تتطلب صلاحيات المشرف.

### خطوات التشغيل:

1. **استنساخ المستودع (Clone Repository):**
   ```bash
   git clone https://github.com/your-username/wifi-shop-manager.git
   cd wifi-shop-manager
   ```

2. **إنشاء بيئة عمل افتراضية (Virtual Environment) وتفعيلها:**
   ```bash
   python -m venv venv
   # في ويندوز:
   .\venv\Scripts\activate
   ```

3. **تثبيت المتطلبات (Install Dependencies):**
   ```bash
   pip install -r requirements.txt
   ```

4. **تشغيل البرنامج (Run Application):**
   ```bash
   # تأكد من تشغيل التيرمينال بصلاحية Administrator
   python src/main.py
   ```

---

<a name="building-exe"></a>
## 📦 بناء الملف التنفيذي محلياً (.exe)

إذا أردت تجربة تحويل الكود إلى تطبيق تنفيذي جاهز يعمل بدون الحاجة لتثبيت بايثون:

1. قم بتشغيل الملف المساعد:
   ```cmd
   build_exe.bat
   ```
2. أو عبر تنفيذ أمر `pyinstaller` مباشرة:
   ```cmd
   pyinstaller --noconfirm --onedir --windowed --name "WiFiShopManager" --add-data "src/assets;assets" src/main.py
   ```
3. ستجد الملف التنفيذي الناتج داخل المجلد:
   `dist\WiFiShopManager\WiFiShopManager.exe`

---

<a name="github-releases"></a>
## 🤖 النشر الآلي والتحديثات عبر GitHub Releases

تم إعداد المشروع بملف سير عمل أوتوماتيكي عبر **GitHub Actions** (`.github/workflows/release.yml`). بمجرد رفع مشروعك على GitHub، لن تحتاج إلى بناء ملف الـ `.exe` يدوياً!

### طريقة إطلاق نسخة جديدة (Release):
1. قم برفع أي تعديلات على الفرع الرئيسي:
   ```bash
   git add .
   git commit -m "Update features and stability"
   git push origin main
   ```
2. أضف وسم الإصدار (Tag) وارفعه إلى GitHub:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. سيقوم خادم GitHub تلقائياً بـ:
   - تشغيل بيئة ويندوز سحابية نظيفة.
   - تثبيت كافة الحزم وبناء ملف `WiFiShopManager.exe`.
   - ضغطه في ملف ZIP باسم `WiFiShopManager-Windows.zip`.
   - إنشاء صفحة إصدار جديدة في **Releases** برابط تحميل مباشر للمستخدمين!

---

<a name="license"></a>
## 📄 الترخيص (License)

هذا المشروع مرخص تحت رخصة **MIT**. يمكنك استخدامه، تعديله، وتوزيعه بحرية لأغراض شخصية أو تجارية. راجع ملف [LICENSE](LICENSE) لمزيد من التفاصيل.
