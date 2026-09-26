# بسته نهایی تحویل سامانه تحلیل حساسیت درجه‌بندی شعب

## 1. مرجع نسخه تحویلی
- Repository: `shariati1985/Grading`
- Branch تحویل: `handover/grading-sensitivity-v1.0.0`
- Version: `1.0.0`
مرجع اصلی سورس، **HEAD همین Branch تحویلی** است. هر ZIP یا Release رسمی باید از HEAD مورد تأیید این Branch تهیه و SHA آن در صورتجلسه یا Release ثبت شود.

## 2. اقلام سورس کد
پکیج سورس شامل موارد زیر است:
- `app.py`
- `config/`
- `data/`
- `domain/`
- `engine/`
- `pages/`
- `persistence/`
- `services/`
- `ui/`
- `tests/`
- `requirements.txt`
- `requirements-dev.txt`
- `.env.example`
- `VERSION`
- `README.md`

## 3. مستندات اصلی تحویل
- `docs/DEPLOYMENT_HANDOVER.md` — الزامات استقرار و تحویل Production
- `docs/DATA_CONTRACT.md` — قرارداد داده
- `docs/INTEGRATION_CONTRACT.md` — قرارداد Integration
- `docs/ACCESS_CONTROL_CONTRACT.md` — Data Scope و Scenario Ownership
- `docs/HOME_DASHBOARD_SPEC.md` — مشخصات صفحه اول مدیریتی
- `docs/GRADING_DASHBOARD_DB_CONTRACT.md` — Contract اتصال به Database داشبورد درجه‌بندی

## 4. معماری Integration مورد توافق
- AD: Authentication
- HRM: تعیین جایگاه سازمانی کاربر و Data Scope
- Database داشبورد درجه‌بندی: اطلاعات شعب، مناطق، Hierarchy شعب، شاخص‌ها، امتیاز، Rank، Grade، Period و History
- Database سامانه تحلیل حساسیت: سناریوها، نتایج، Version، Ownership و Audit Trail

## 5. قواعد دسترسی مورد توافق
- کاربر شعبه: فقط شعبه خود
- کاربر منطقه: شعب زیرمجموعه منطقه
- کاربر ستادی: کل شبکه
- سناریوهای ذخیره‌شده: هر کاربر فقط سناریوهای خود را مشاهده و مدیریت می‌کند.

## 6. مواردی که در Repository تحویلی قرار نمی‌گیرند
- داده واقعی بانک
- `Data.xlsx`
- فایل‌های خروجی تولیدشده
- Password
- Token
- Connection String واقعی
- Certificate
- Secrets
- Database محلی Production
- Logهای حاوی اطلاعات حساس

## 7. مواردی که فناوری بانک باید تکمیل کند
- اتصال واقعی AD
- اتصال واقعی HRM
- پیاده‌سازی SQL Server Adapter برای Database داشبورد درجه‌بندی
- پیاده‌سازی `SqlServerScenarioRepository`
- تنظیم Data Scope در Production
- Database و Schema فیزیکی
- Secrets Management
- Logging و Monitoring
- Backup و Restore
- Security Hardening
- DEV / TEST / UAT / PROD
- UAT و Production Release

## 8. وضعیت Validation
Source Compile در آخرین Validation موفق بوده است.

Test Suite فعلی هنوز بخشی از Regression Testهای قدیمی را به فایل محلی `Data.xlsx` وابسته دارد. چون این فایل عمداً از Branch تحویلی حذف شده است، اجرای کامل CI بدون Dataset تستی مصوب سبز نیست.

این موضوع مانع تحویل Contractها و سورس نیست، اما پیش از Release عملیاتی Production باید یکی از این اقدامات انجام شود:
- تأمین Dataset تستی Sanitized مورد تأیید بانک؛ یا
- بازطراحی Test Fixtureها به داده Synthetic بدون استفاده از داده واقعی بانک.

نباید برای سبزکردن CI، فایل واقعی بانک مجدداً وارد Git شود.

## 9. کنترل امنیت Repository
در زمان تهیه این بسته، Repository در GitHub با Visibility برابر Public مشاهده شده است.

فایل‌های Excel در تاریخچه قدیمی Repository وجود داشته‌اند. حذف فایل از Branch تحویلی به معنی حذف آن از Git History نیست.

قبل از تحویل رسمی، اگر هر یک از فایل‌های قبلی حاوی داده واقعی یا محرمانه بانک بوده‌اند، اقدامات زیر باید با هماهنگی فناوری/امنیت انجام شود:
- Private کردن Repository مطابق سیاست بانک
- بررسی Git History
- در صورت لزوم Purge تاریخچه در تمام Refهای مربوط
- بررسی Fork/Cache احتمالی
- Secret Scan و Data Exposure Review

تغییر مخرب History بدون تأیید فناوری/امنیت انجام نشود.

## 10. روش تحویل پیشنهادی
مرجع اصلی:
- Git Repository روی Branch تحویلی

نسخه بایگانی رسمی:
- ZIP/Release از نسخه نهایی مورد تأیید
- نام پیشنهادی: `grading-sensitivity-v1.0.0.zip`

پس از تأیید فناوری و UAT، Tag نهایی:
- `grading-sensitivity-v1.0.0`

## 11. معیار خاتمه Handover
Handover زمانی کامل تلقی می‌شود که:
1. فناوری دسترسی به Repository یا ZIP رسمی داشته باشد.
2. مستندات فوق تحویل شده باشند.
3. Connection و Credentialها خارج از Git ارائه شوند.
4. Integrationهای AD/HRM/Database در محیط بانک پیاده‌سازی شوند.
5. UAT تأیید شود.
6. Release/Tag نهایی Production ثبت شود.
