# پلتفرم تحلیل حساسیت درجه‌بندی شعب

## نسخه تحویلی
- نسخه Handover: **1.0.0**
- Branch تحویلی: `handover/grading-sensitivity-v1.0.0`
- Branch مبنا: `feature/multi-branch-finalization`
- Commit مبنا: `df1bedb5de3098d3db7c5def77782d942121669b`

## هدف
این Repository شامل نسخه فعلی سامانه تحلیل حساسیت درجه‌بندی شعب است و اجزای اصلی شامل موتور رتبه‌بندی، منطق سناریوها، رابط کاربری Streamlit، لایه Service، لایه دسترسی به داده، Persistence محلی و تست‌های خودکار را در بر می‌گیرد.

## وضعیت فعلی فنی
سامانه در وضعیت Prototype عملیاتی و آماده تحویل برای تکمیل Production است. منطق کسب‌وکار و جریان‌های اصلی کاربر پیاده‌سازی شده‌اند، اما موارد زیر باید توسط فناوری بانک تکمیل شوند:

1. اتصال احراز هویت سازمانی و Authorization.
2. اتصال Production به AD و HRM.
3. اتصال به Database داشبورد درجه‌بندی شعب.
4. پیاده‌سازی Persistence سناریوها روی SQL Server.
5. تکمیل زیرساخت، Secrets Management، Logging، Monitoring، Backup، Security Hardening و Deployment.
6. اجرای UAT و کنترل‌های انتشار Production.

## اجزای اصلی
- `app.py`: نقطه ورود Streamlit.
- `engine/`: منطق رتبه‌بندی، مقایسه، حساسیت و سناریو.
- `domain/`: قراردادها و ساختارهای Domain.
- `services/`: Serviceهای کاربردی و Workspace.
- `data/`: قراردادهای داده و Repositoryها.
- `persistence/`: Persistence محلی SQLite و اسکلت SQL Server.
- `ui/`: اجزای قابل استفاده مجدد UI.
- `pages/`: صفحات Streamlit.
- `tests/`: تست‌های خودکار.
- `docs/`: مستندات معماری، استقرار و Handover.

## اجرای نسخه Local
1. Python 3.13 یا نسخه سازگار نصب شود.
2. Virtual Environment ایجاد و فعال شود.
3. وابستگی‌ها نصب شوند:
   ```bash
   pip install -r requirements.txt
   ```
4. برای اجرای Local، فایل مبنای `Data.xlsx` در Root پروژه قرار گیرد.
5. سامانه اجرا شود:
   ```bash
   streamlit run app.py
   ```

> فایل `Data.xlsx` عمداً در Branch تحویلی نگهداری نمی‌شود. در صورت نیاز، داده تستی یا Sanitized باید جداگانه تأمین شود.

## مرز Production
در Production، اطلاعات اصلی شعب و درجه‌بندی باید از Database داشبورد درجه‌بندی خوانده شود، احراز هویت از AD انجام شود و ساختار سازمانی کاربران جهت تعیین Data Scope از HRM تأمین گردد. سناریوهای ذخیره‌شده نیز باید در Database مستقل سامانه تحلیل حساسیت نگهداری شوند.

تکمیل Integrationها نباید موجب تغییر بدون مجوز در منطق مصوب درجه‌بندی و سناریوها شود.

## مستندات تحویل
- `docs/DEPLOYMENT_HANDOVER.md` — الزامات استقرار و تحویل Production
- `docs/DATA_CONTRACT.md` — قرارداد داده ورودی و خروجی
- `docs/INTEGRATION_CONTRACT.md` — قرارداد Integration با سامانه‌ها و Databaseها
- `docs/ACCESS_CONTROL_CONTRACT.md` — قواعد Data Scope و مالکیت خصوصی سناریوها
- `docs/HOME_DASHBOARD_SPEC.md` — مشخصات صفحه اول مدیریتی و منابع داده آن

## امنیت
Password، Token، Connection String، Certificate، اطلاعات واقعی بانک و سایر Secrets نباید در Git نگهداری شوند. مقادیر Production باید از طریق سازوکار مورد تأیید بانک برای Configuration و Secrets Management تأمین شوند.
