# قرارداد اتصال به Database داشبورد درجه‌بندی شعب

## 1. هدف
این سند Contract منطقی موردنیاز سامانه تحلیل حساسیت برای خواندن اطلاعات رسمی از Database داشبورد درجه‌بندی شعب را مشخص می‌کند.

هدف این Contract تعیین **داده موردنیاز Application** است، نه تعیین ساختار فیزیکی SQL Server. نام واقعی Table، View، Stored Procedure یا Schema باید توسط فناوری بانک نهایی شود.

## 2. مبنای سند
سند عملکردی داشبورد درجه‌بندی، مدل منطقی را بر شش مجموعه داده اصلی بنا کرده است:

- `Fact_Branch_Ranking`
- `Fact_Indicator_Scores`
- `Dim_Branch`
- `Dim_Indicator`
- `Dim_Grade`
- `Dim_Period`

همان سند تصریح می‌کند که نحوه ایجاد فیزیکی این جداول در SQL Server در دامنه سند نیست.

سامانه تحلیل حساسیت باید از همین منطق داده استفاده کند و محاسبات رسمی رتبه، Grade، Normalization و Weighting را مجدداً انجام ندهد.

## 3. داده‌های رسمی رتبه‌بندی شعب

### Dataset منطقی رتبه‌بندی
برای هر شعبه و هر Period حداقل اطلاعات زیر موردنیاز است:

| فیلد Application | مفهوم | الزام |
|---|---|---|
| `branch_id` | شناسه شعبه | الزامی |
| `period_id` | شناسه دوره | الزامی |
| `final_score` | امتیاز نهایی رسمی | الزامی |
| `final_rank` | رتبه رسمی شعبه | الزامی |
| `grade` | درجه رسمی شعبه | الزامی |
| `excellent_group` | گروه ممتاز / ممتاز ویژه در صورت استفاده | اختیاری برای UI |

این Dataset متناظر با مفهوم `Fact_Branch_Ranking` در سند داشبورد است.

قاعده یکتایی:
```text
(branch_id, period_id) = unique
```

## 4. داده‌های شاخص‌های هر شعبه

### Dataset منطقی شاخص‌ها
برای هر شعبه، Period و Indicator حداقل اطلاعات زیر موردنیاز است:

| فیلد Application | مفهوم | الزام |
|---|---|---|
| `branch_id` | شناسه شعبه | الزامی |
| `period_id` | شناسه دوره | الزامی |
| `indicator_id` | شناسه شاخص | الزامی |
| `raw_value` | مقدار خام | الزامی |
| `log_value` | مقدار Log | الزامی |
| `normalized_score` | امتیاز Normalize شده رسمی | الزامی |
| `weighted_contribution` | سهم وزنی شاخص | الزامی |
| `indicator_rank` | رتبه شعبه در آن شاخص | الزامی |

این Dataset متناظر با مفهوم `Fact_Indicator_Scores` در سند داشبورد است.

قاعده یکتایی:
```text
(branch_id, period_id, indicator_id) = unique
```

برای مدل فعلی، هر `branch_id + period_id` باید 8 رکورد شاخص داشته باشد.

## 5. اطلاعات مرجع شعب و مناطق

### 5.1 اطلاعات پایه شعب
سند داشبورد فعلی در `Dim_Branch` حداقل `Branch_ID` و `Name_Branch` را مشخص کرده است.

برای نیاز سامانه تحلیل حساسیت، Contract شعب باید حداقل به شکل زیر توسعه یابد:

| فیلد Application | مفهوم | منبع الزام |
|---|---|---|
| `branch_id` | شناسه شعبه | سند داشبورد |
| `branch_name` | نام شعبه | سند داشبورد |
| `region_id` | شناسه منطقه | نیاز تکمیلی سامانه تحلیل حساسیت |
| `region_name` | نام منطقه | نیاز تکمیلی سامانه تحلیل حساسیت |

### 5.2 ارتباط منطقه و شعب زیرمجموعه
طبق تصمیم Business، منبع تشخیص شعب زیرمجموعه هر منطقه **Database داشبورد درجه‌بندی** است و نه HRM.

بنابراین Adapter باید بتواند حداقل این Contract را پاسخ دهد:

```text
region_id -> list[branch_id]
```

ساختار فیزیکی این ارتباط آزاد است. فناوری می‌تواند آن را:
- در `Dim_Branch` نگهداری کند؛
- در یک View منطقی ارائه دهد؛
- یا از یک جدول Hierarchy موجود استخراج کند.

سامانه تحلیل حساسیت فقط Contract خروجی را مصرف می‌کند.

## 6. اطلاعات مرجع شاخص‌ها
Dataset مرجع Indicator باید حداقل شامل موارد زیر باشد:

| فیلد | مفهوم |
|---|---|
| `indicator_id` | شناسه شاخص |
| `indicator_name` | عنوان شاخص |
| `weight` | وزن مصوب |
| `direction` | `benefit` یا `cost` |
| `indicator_order` | ترتیب نمایش |

این Dataset متناظر با `Dim_Indicator` است.

## 7. اطلاعات مرجع Grade
Dataset مرجع Grade باید حداقل شامل موارد زیر باشد:

| فیلد | مفهوم |
|---|---|
| `grade_id` | شناسه Grade |
| `grade_label` | عنوان Grade |
| `grade_order` | ترتیب نمایش |
| `target_percentage` | درصد هدف |

این Dataset متناظر با `Dim_Grade` است.

## 8. اطلاعات Period
Dataset Period باید حداقل شامل موارد زیر باشد:

| فیلد | مفهوم |
|---|---|
| `period_id` | شناسه دوره |
| `year` | سال |
| `month` | ماه |
| `period_label` | عنوان نمایشی |

این Dataset متناظر با `Dim_Period` است.

## 9. Data Setهای موردنیاز سامانه تحلیل حساسیت

Application باید بدون وابستگی به نام فیزیکی Table/View بتواند عملیات منطقی زیر را انجام دهد:

### 9.1 دریافت Periodهای موجود
```text
get_available_periods()
-> period_id, period_label, year, month
```

### 9.2 دریافت ساختار شعب
```text
get_branch_directory()
-> branch_id, branch_name, region_id, region_name
```

### 9.3 دریافت شعب یک منطقه
```text
get_region_branches(region_id)
-> branch_id[]
```

### 9.4 دریافت وضعیت رسمی شعب در یک Period
```text
get_branch_rankings(period_id, permitted_branch_ids)
-> branch_id, final_score, final_rank, grade, ...
```

### 9.5 دریافت اطلاعات شاخص‌ها
```text
get_branch_indicators(period_id, permitted_branch_ids)
-> branch_id, indicator_id, raw_value, normalized_score, weighted_contribution, indicator_rank, ...
```

### 9.6 دریافت تعاریف Indicator
```text
get_indicator_definitions()
-> indicator_id, indicator_name, weight, direction, indicator_order
```

## 10. نیاز صفحه اول سامانه تحلیل حساسیت
پس از اعمال Data Scope، صفحه اول از Data Setهای فوق فقط Aggregation انجام می‌دهد.

### KPIها
- تعداد شعب در Scope
- تعداد مناطق در Scope
- میانگین `final_score`
- Period فعال
- تعداد سناریوهای ذخیره‌شده کاربر از Database تحلیل حساسیت

### نمودارها
- توزیع `grade`
- میانگین `final_score` به تفکیک منطقه
- میانگین `normalized_score` برای 8 Indicator
- تغییر Rank نسبت به Period قبل، در صورت وجود داده تاریخی

## 11. Rank Change و داده تاریخی
سند منطقی داشبورد دارای Fact رتبه‌بندی به تفکیک Period و Dimension دوره است؛ بنابراین تاریخچه Periodها قابلیت مقایسه را فراهم می‌کند.

برای سامانه تحلیل حساسیت دو روش قابل قبول است:

### روش A — پیشنهاد ترجیحی
Adapter دو Period متوالی را می‌خواند و در Service Presentation مقدار تغییر Rank را محاسبه می‌کند:

```text
rank_change = previous_rank - current_rank
```

عدد مثبت به معنی بهبود رتبه است.

این محاسبه **تغییر در منطق مدل نیست**؛ صرفاً مقایسه دو خروجی رسمی ثبت‌شده است.

### روش B
Database/View مقدار `previous_rank` و `rank_change` را مستقیماً ارائه دهد.

هر دو روش قابل قبول‌اند، مشروط بر اینکه Rankهای پایه مستقیماً از Fact رسمی داشبورد آمده باشند.

## 12. اعمال Data Scope
Flow دسترسی:

```text
AD
 -> Authentication
 -> HRM
 -> organization_scope_level / organization_reference
 -> Dashboard DB
 -> permitted_branch_ids
 -> Queryهای رتبه‌بندی و شاخص‌ها
```

قواعد:
- `branch`: فقط شعبه کاربر
- `region`: شعب زیرمجموعه منطقه
- `head_office`: کل شعب

فیلتر Branch باید قبل از تحویل Dataset به UI اعمال شود.

## 13. ممنوعیت محاسبه موازی
Adapter و صفحه اول مجاز نیستند موارد زیر را مستقلاً از Raw Data بازتولید کنند:

- `final_score`
- `final_rank`
- `grade`
- `normalized_score`
- `weighted_contribution`
- `indicator_rank`

این مقادیر باید از خروجی رسمی مدل/Database داشبورد خوانده شوند.

## 14. کنترل‌های Data Quality
حداقل کنترل‌های لازم:

- `branch_id` خالی نباشد.
- `branch_id + period_id` در Ranking تکراری نباشد.
- `branch_id + period_id + indicator_id` در Indicator Fact تکراری نباشد.
- هر شعبه در مدل فعلی برای هر Period دارای 8 Indicator باشد.
- `normalized_score` در محدوده 1 تا 1000 باشد.
- Weightهای Indicator با نسخه مصوب مدل تطابق داشته باشند.
- Branchهای منتسب به Region معتبر باشند.
- Period درخواستی وجود داشته باشد.
- داده Scope کاربر خارج از `permitted_branch_ids` به Application تحویل نشود.

## 15. مواردی که باید با فناوری بانک نهایی شوند
این Contract عمداً موارد زیر را تعیین نمی‌کند:

- نام واقعی Database
- نام Schema
- نام View/Table
- Driver اتصال
- Connection String
- Stored Procedure
- Indexها
- روش Cache
- Service Account
- Timeout
- نحوه مدیریت Connection Pool

این موارد Technical Design هستند و باید توسط فناوری بانک نهایی شوند، بدون تغییر Contract منطقی فوق.
