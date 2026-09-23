# قرارداد Integration

## 1. هدف
این سند مرزهای Integration سامانه تحلیل حساسیت درجه‌بندی شعب با سامانه‌ها و Databaseهای بانک را مشخص می‌کند و مسئولیت‌های فنی را از قواعد کسب‌وکار جدا نگه می‌دارد.

## 2. مرزهای Integration

| حوزه | وضعیت فعلی | هدف Production | وضعیت در Handover |
|---|---|---|---|
| Authentication | Local User | Active Directory (AD) | Adapter سازمانی باید تکمیل شود |
| تعیین جایگاه سازمانی کاربر | Local Metadata | HRM | HRM Adapter باید تکمیل شود |
| اطلاعات شعب، مناطق و داده درجه‌بندی | Excel محلی | Database داشبورد درجه‌بندی شعب | نقطه اتصال ایجاد شده؛ پیاده‌سازی Production باقی است |
| Persistence سناریو | SQLite محلی | SQL Server سامانه تحلیل حساسیت | Contract موجود؛ پیاده‌سازی Production باقی است |
| Runtime Configuration | Local Default / Environment | سازوکار Deployment بانک | Externalized شده |
| Logging / Audit / Monitoring | محدود به نسخه فعلی | سرویس‌های مرکزی بانک | باید تکمیل شود |

## 3. معماری منابع Production
معماری مورد توافق شامل این منابع است:

- **AD** برای Authentication.
- **HRM** برای تعیین جایگاه سازمانی کاربر و سطح Data Scope.
- **Database داشبورد درجه‌بندی شعب** برای اطلاعات شعب، مناطق، شعب زیرمجموعه، شاخص‌ها، امتیازها، رتبه‌ها، درجات، دوره‌ها، تاریخچه و اطلاعات تحلیلی صفحه اول.
- **Database سامانه تحلیل حساسیت** برای نگهداری سناریوها، نسخه‌ها، تغییرات، نتایج و Audit Trail.

HRM منبع اطلاعات شعب و منطقه نیست. HRM فقط مشخص می‌کند کاربر از نظر سازمانی شعبه‌ای، منطقه‌ای یا ستادی است. سپس فهرست واقعی شعب مجاز از Database داشبورد درجه‌بندی تعیین می‌شود.

سناریوهای ذخیره‌شده کاملاً شخصی هستند و به مالک سناریو تعلق دارند.

برای جزئیات دسترسی به `docs/ACCESS_CONTROL_CONTRACT.md` مراجعه شود.

## 4. اتصال به Database داشبورد درجه‌بندی

### Contract Application
Application در سطح Repository متدی معادل زیر فراخوانی می‌کند:

```python
load_branch_data(period: str | None) -> DataFrame
```

خروجی باید مطابق `docs/DATA_CONTRACT.md` باشد.

### وضعیت فعلی
کلاس `SqlServerBranchRepository` به‌عنوان مرز اتصال SQL Server وجود دارد، اما تا زمان انتخاب Driver و Query Strategy مورد تأیید فناوری بانک، پیاده‌سازی Production آن تکمیل نشده است.

Runtime Settingهای مرتبط:
- `DATA_SOURCE_TYPE=sqlserver`
- `DATA_SOURCE_CONNECTION_STRING`
- `DATA_SOURCE_TABLE_OR_VIEW`
- `BASE_PERIOD`

### الزامات پیاده‌سازی
پیاده‌سازی Production باید:
- از Parameterized SQL یا ORM/Driver مورد تأیید استفاده کند.
- در صورت چنددوره‌ای بودن منبع، Period درخواستی را فیلتر کند.
- فقط Schema استاندارد را به Engine تحویل دهد.
- شناسه شعب را بدون تغییر معنایی حفظ کند.
- Credential را در Source Code قرار ندهد.
- خطاهای Connection و Schema را صریح گزارش کند.
- Timeout و Logging مطابق استاندارد بانک داشته باشد.

نام View، Stored Procedure یا ساختار فیزیکی Database باید با فناوری بانک نهایی شود و در این Handover فرض نشده است.

## 5. اتصال Persistence سناریوها

### وضعیت فعلی
نسخه Local از SQLite استفاده می‌کند.

### هدف Production
`SqlServerScenarioRepository` باید عملیات زیر را روی SQL Server پیاده‌سازی کند:
- ایجاد سناریو
- ویرایش سناریو
- دریافت سناریو
- فهرست سناریوها
- حذف سناریو
- Archive سناریو
- ایجاد نسخه/Copy سناریو

پیاده‌سازی Production باید موارد زیر را حفظ کند:
- Ownership Check
- `requesting_user_id`
- Optimistic Concurrency با `row_version`
- Atomic Update
- Server-Side Pagination
- ذخیره تغییرات سناریو
- ذخیره خلاصه نتایج

کلاس فعلی SQL Server فقط Skeleton است و نباید به‌عنوان Persistence کامل Production تلقی شود.

Runtime Settingهای مرتبط:
- `SCENARIO_DB_TYPE=sqlserver`
- `SCENARIO_DB_CONNECTION_STRING`

## 6. اتصال AD و HRM

### مدل کاربر
`CurrentUser` در Application شامل موارد زیر است:
- `user_id`
- `display_name`
- `roles`
- اطلاعات اختیاری مرتبط با شعبه

### Production
با `AUTH_MODE=enterprise`:
1. کاربر از طریق AD احراز هویت می‌شود.
2. شناسه کاربر به Contract داخلی `CurrentUser` نگاشت می‌شود.
3. HRM جایگاه سازمانی کاربر را مشخص می‌کند.
4. Application جایگاه را به یکی از Scopeهای `branch`، `region` یا `head_office` تبدیل می‌کند.
5. فهرست شعب مجاز از Database داشبورد درجه‌بندی دریافت می‌شود.

جزئیات Protocol، Endpoint، Table، Field و Credential مربوط به AD و HRM باید توسط فناوری بانک تعیین شود و در این مستند فرض نشده است.

## 7. Authorization و Data Scope
Authentication و Authorization دو موضوع مجزا هستند.

قواعد Data Scope مورد توافق:
- کاربر شعبه → فقط شعبه خودش
- کاربر منطقه → شعب زیرمجموعه همان منطقه
- کاربر ستادی → کل شبکه شعب

جایگاه سازمانی از HRM می‌آید، اما شعب زیرمجموعه و Hierarchy از Database داشبورد درجه‌بندی تعیین می‌شوند.

Functional Role از Data Scope جدا است.

مالکیت سناریو نیز مستقل است: هر کاربر فقط سناریوهای خود را مشاهده و مدیریت می‌کند؛ حتی اگر کاربر ستادی Data Scope کل شبکه داشته باشد.

## 8. Configuration و Secrets
مقادیر Production باید خارج از Source Code تزریق شوند.

`.env.example` فقط نام Settingها را مستند می‌کند و نباید مقدار واقعی Credential در آن قرار گیرد.

موارد اصلی:
- Environment و Version
- Period مبنا
- نوع و Connection منبع داده
- نوع و Connection Database سناریوها
- Authentication Mode
- اطلاعات لازم برای Enterprise Identity

## 9. رفتار خطا
در Production نباید Fallback پنهان انجام شود:
- SQL Server به Excel
- Enterprise Authentication به Local User
- SQL Server Persistence به SQLite

اگر Adapter Production پیاده‌سازی یا تنظیم نشده باشد، سامانه باید صریحاً Fail شود.

## 10. الزامات امنیتی
فناوری بانک باید استانداردهای بانک را در این حوزه‌ها اعمال کند:
- TLS / HTTPS
- Network Segmentation و Firewall
- Service Account
- Least Privilege
- Credential Rotation
- Secret Storage
- Database Permission
- Session Security
- Audit Log
- Vulnerability Assessment
- Backup و Restore

## 11. معیارهای پذیرش Integration
Integration برای UAT زمانی قابل پذیرش است که:
1. Application بدون فایل داده Production محلی اجرا شود.
2. هویت کاربر از AD به Contract داخلی نگاشت شود.
3. جایگاه سازمانی از HRM تعیین شود.
4. Data Scope صحیح اعمال شود.
5. داده شعب از Database داشبورد درجه‌بندی خوانده شود.
6. نتایج مدل برای Dataset یکسان با Baseline مصوب یکسان باشد.
7. سناریوها پس از Restart باقی بمانند.
8. Ownership و Concurrency روی SQL Server صحیح عمل کند.
9. هیچ Secret واقعی در Git وجود نداشته باشد.
10. خطاهای Integration قابل Logging و Monitoring باشند.
11. UAT بدون تغییر ناخواسته در منطق محاسبات تأیید شود.

## 12. مسئولیت‌ها
- **Business Owner:** قواعد درجه‌بندی، مفهوم شاخص‌ها، Weightها، منطق سناریوها، قواعد دسترسی و تأیید UAT.
- **فناوری بانک:** AD، HRM Integration، Database Integration، Persistence، Security، Deployment، Monitoring، Backup و پشتیبانی عملیاتی.
- هر تغییر در مرز Business و Technical باید مستند و پیش از Production تأیید شود.
