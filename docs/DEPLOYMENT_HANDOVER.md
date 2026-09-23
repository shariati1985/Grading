# سند تحویل و استقرار Production

## 1. مبنای تحویل
این سند مربوط به نسخه زیر است:
- Repository: `shariati1985/Grading`
- Branch: `handover/grading-sensitivity-v1.0.0`
- Version: `1.0.0`
- Commit مبنا قبل از آماده‌سازی Handover: `df1bedb5de3098d3db7c5def77782d942121669b`

این Branch به‌عنوان نسخه کنترل‌شده سورس برای تحویل به فناوری بانک در نظر گرفته شده است.

## 2. اجزای پیاده‌سازی‌شده
در نسخه فعلی موارد زیر وجود دارد:
- منطق درجه‌بندی و رتبه‌بندی شعب
- اجرای سناریو و مقایسه نتایج
- تحلیل حساسیت تک‌شعبه‌ای
- سناریوی چندشعبه‌ای
- سناریوی Target Rank
- ذخیره و بازیابی سناریو
- رابط کاربری Streamlit
- Persistence محلی سناریوها با SQLite
- قراردادهای داده و Repository
- تست‌های خودکار برای منطق محاسبات، Persistence، Workflow و UI

## 3. محدودیت‌های نسخه Pre-Production

### 3.1 منبع داده
نسخه Local قابلیت استفاده از `Data.xlsx` را دارد. در Production، منبع اصلی اطلاعات شعب و درجه‌بندی باید Database داشبورد درجه‌بندی شعب باشد.

### 3.2 Persistence سناریوها
نسخه Local از `SQLiteScenarioRepository` استفاده می‌کند. این روش برای Production چندکاربره مناسب نیست.

کلاس `SqlServerScenarioRepository` به‌عنوان Contract و اسکلت فنی وجود دارد، اما پیاده‌سازی Production آن باید توسط فناوری بانک تکمیل و تست شود.

### 3.3 احراز هویت و دسترسی
Integration سازمانی با AD و HRM باید در Production تکمیل شود:
- AD برای Authentication
- HRM برای تعیین جایگاه سازمانی و Data Scope
- Database داشبورد درجه‌بندی برای تعیین شعب مجاز هر Scope

## 4. اقدامات موردنیاز فناوری بانک
1. ایجاد محیط‌های DEV، TEST، UAT و PROD.
2. اتصال Authentication به AD.
3. اتصال HRM برای استخراج جایگاه سازمانی کاربران.
4. پیاده‌سازی Data Scope مصوب.
5. اتصال به Database داشبورد درجه‌بندی شعب.
6. پیاده‌سازی Persistence سناریوها روی SQL Server.
7. Externalize کردن Runtime Configuration و Secrets.
8. تنظیم HTTPS، Reverse Proxy، DNS داخلی و کنترل‌های شبکه.
9. پیاده‌سازی Centralized Logging و Audit Log.
10. پیاده‌سازی Monitoring و Alerting.
11. تعریف Backup، Restore و Disaster Recovery.
12. انجام Security Review و Vulnerability Assessment.
13. اجرای Automated Testها و سناریوهای UAT.
14. اخذ تأیید Business Owner پیش از انتشار Production.

## 5. مالکیت قواعد کسب‌وکار
قواعد رتبه‌بندی، درجه‌بندی، Normalization، Weighting و محاسبات سناریو متعلق به Business است. هرگونه Refactor یا Integration فنی نباید به‌صورت پنهان این قواعد را تغییر دهد.

هر تغییر در منطق محاسبات نیازمند:
- تأیید Business Owner
- Regression Test
- ثبت نسخه تغییر

## 6. مدیریت داده و اطلاعات محرمانه
موارد زیر نباید داخل Source Control قرار گیرند:
- داده واقعی بانک
- Password و Token
- Connection String واقعی
- Certificate
- Database محلی Production
- Log حاوی اطلاعات حساس
- فایل‌های Secret Environment

Branch تحویلی عمداً موارد زیر را نگهداری نمی‌کند:
- `Data.xlsx`
- `Branch_Ranking_New_Model.xlsx`
- Databaseهای SQLite محلی
- خروجی‌های تولیدی CSV / Power BI
- Local User Configuration
- Logها و Secrets

## 7. کنترل‌های لازم پیش از Production
حداقل موارد زیر باید تأیید شوند:
- نتایج رتبه‌بندی مبنا با خروجی مرجع مصوب یکسان باشد.
- نتایج سناریو با نسخه Handover یکسان باشد.
- Save / Restore / Version روی SQL Server صحیح عمل کند.
- رفتار چندکاربره و Concurrency تست شود.
- Data Scope و Permissionها enforce شوند.
- مالکیت خصوصی سناریوها enforce شود.
- Audit Log کامل باشد.
- هیچ Secretای در Git وجود نداشته باشد.
- Monitoring و Backup عملیاتی باشند.
- UAT توسط Business Owner تأیید شود.

## 8. کنترل Release
پس از تکمیل Integration و UAT، نسخه Production باید به‌صورت Release/Tag کنترل‌شده از Branch تحویلی ایجاد شود. استقرار مستقیم از Working Branch توصیه نمی‌شود.
