# قرارداد داده

## 1. هدف
این سند حداقل داده موردنیاز موتور درجه‌بندی و تحلیل حساسیت شعب را مشخص می‌کند. در Production، منبع اصلی اطلاعات شعب و درجه‌بندی Database داشبورد درجه‌بندی شعب است. Adapter متصل به سامانه باید داده را مطابق Schema استاندارد زیر در اختیار Application قرار دهد، بدون اینکه منطق کسب‌وکار را تغییر دهد.

## 2. Schema استاندارد ورودی

| فیلد | مفهوم | نوع منطقی | الزامی | قاعده فعلی |
|---|---|---|---|---|
| `branch_id` | کد شعبه | string | بله | خالی نباشد و Unique باشد؛ صفرهای ابتدایی حفظ شوند. |
| `branch_name` | نام شعبه | string | بله | خالی نباشد. |
| `region` | منطقه | string | بله | مقدار متنی منطقه. |
| `avg_deposits` | میانگین سپرده‌ها | numeric | بله | مقدار عددی. |
| `deposit_count` | تعداد سپرده‌ها | numeric | بله | حداقل مقدار مجاز در Scenario Validation برابر صفر است. |
| `avg_loans` | میانگین تسهیلات | numeric | بله | حداقل مقدار مجاز صفر است. |
| `loan_count` | تعداد تسهیلات | numeric | بله | حداقل مقدار مجاز صفر است. |
| `avg_commitments` | میانگین تعهدات | numeric | بله | حداقل مقدار مجاز صفر است. |
| `commitment_count` | تعداد تعهدات | numeric | بله | حداقل مقدار مجاز صفر است. |
| `transaction_volume` | حجم عملیات | numeric | بله | حداقل مقدار مجاز صفر است. |
| `profit_loss` | سود (زیان) | numeric | بله | مقدار منفی مجاز است. |

ترتیب استاندارد فیلدها:

```text
branch_id
branch_name
region
avg_deposits
deposit_count
avg_loans
loan_count
avg_commitments
commitment_count
transaction_volume
profit_loss
```

## 3. Mapping نسخه Excel فعلی

| ستون فارسی | فیلد استاندارد |
|---|---|
| کد شعبه | `branch_id` |
| نام شعبه | `branch_name` |
| منطقه | `region` |
| میانگین سپرده ها | `avg_deposits` |
| تعداد سپرده ها | `deposit_count` |
| میانگین تسهیلات | `avg_loans` |
| تعداد تسهیلات | `loan_count` |
| میانگین تعهدات | `avg_commitments` |
| تعداد تعهدات | `commitment_count` |
| حجم عملیات | `transaction_volume` |
| سود (زیان) | `profit_loss` |

ردیف‌هایی با نام `اوزان`، `وزن`، `weight` یا `weights` در Adapter فعلی Excel به‌عنوان شعبه محسوب نمی‌شوند.

## 4. قواعد شناسه و یکتایی
- `branch_id` شناسه اصلی شعبه در Application است.
- مقدار آن باید به‌صورت Text قابل استفاده باشد.
- صفرهای ابتدایی نباید حذف شوند.
- مقدار خالی مجاز نیست.
- برای یک Population مبنا، `branch_id` تکراری مجاز نیست.
- `branch_name` خالی مجاز نیست.

## 5. مقادیر عددی
در Adapter فعلی Excel:
1. ارقام فارسی و عربی به ارقام لاتین تبدیل می‌شوند.
2. جداکننده‌های رایج هزارگان حذف می‌شوند.
3. علامت‌های مختلف منفی Normalize می‌شوند.
4. Numeric Conversion انجام می‌شود.
5. مقدار خالی یا غیرعددی به `0.0` تبدیل می‌شود.

موتور اصلی نیز در ورودی خود مقادیر غیرعددی شاخص‌ها را به Numeric تبدیل کرده و خطاهای Conversion را با `0.0` جایگزین می‌کند.

این موضوع صرفاً **رفتار فعلی پیاده‌سازی** است. در Production توصیه می‌شود خطاهای Data Quality پیش از رسیدن داده به موتور شناسایی و گزارش شوند. تغییر رفتار Zero-Fill یک تغییر Business Rule محسوب می‌شود و نیازمند تأیید و Regression Test است.

## 6. شاخص‌ها و اوزان مصوب فعلی

| شاخص | Direction | Weight |
|---|---|---:|
| `avg_deposits` | benefit | 0.500 |
| `deposit_count` | benefit | 0.005 |
| `avg_loans` | benefit | 0.260 |
| `loan_count` | benefit | 0.010 |
| `avg_commitments` | benefit | 0.170 |
| `commitment_count` | benefit | 0.010 |
| `transaction_volume` | benefit | 0.015 |
| `profit_loss` | benefit | 0.030 |

مجموع Weightها برابر 1.0 است.

لایه Integration باید Raw Value شاخص‌ها را تحویل دهد و نباید پیش از ورود به موتور، Normalization یا Re-Weighting مستقلی انجام دهد؛ مگر اینکه تغییر مدل به‌صورت رسمی تصویب شده باشد.

## 7. دوره
دوره مبنا از طریق `BASE_PERIOD` قابل تنظیم است.

در Contract فعلی، `period_id` داخل DataFrame ورودی قرار ندارد و Period به‌صورت جداگانه به Repository داده می‌شود. در صورت چنددوره‌ای بودن Database، متد `load_branch_data(period)` باید فقط Population مربوط به Period درخواستی را در Schema استاندارد برگرداند.

## 8. قرارداد خروجی‌های داشبورد

### خلاصه شعب
```text
branch_id
branch_code
branch_name
region_id
region_name
period_id
period_label
final_score
final_rank
grade
previous_rank
rank_change
calculation_timestamp
```

### جزئیات شاخص‌های شعب
```text
branch_id
branch_code
period_id
indicator_id
indicator_name
raw_value
shifted_value
log_value
normalized_score
indicator_rank
weight
weighted_contribution
```

### تعاریف شاخص‌ها
```text
indicator_id
indicator_name
weight
direction
```

### فهرست دوره‌ها
```text
period_id
period_label
```

Dashboard Repository فقط خروجی Engine را ارائه می‌کند و نباید محاسبات مدل را به‌صورت مستقل تکرار کند.

## 9. کنترل‌های پذیرش Data Adapter
پیش از UAT باید حداقل موارد زیر کنترل شوند:
- هر 11 فیلد استاندارد موجود باشد.
- `branch_id` خالی یا تکراری وجود نداشته باشد.
- صفرهای ابتدایی شناسه شعب حفظ شوند.
- نام شعبه خالی نباشد.
- هر 8 شاخص در مرز Application مقدار Numeric داشته باشند.
- Period درخواستی Population صحیح را بازگرداند.
- یک Dataset یکسان، نتایج یکسان با Baseline مصوب ایجاد کند.
- Adapter منبع داده نباید مستقلاً `normalized_score`، رتبه، درجه یا `weighted_score` محاسبه کند.

## 10. کنترل تغییر
تغییر در مفهوم فیلد، واحد اندازه‌گیری، روش تجمیع، Period، Null Handling، Direction شاخص، Weight یا Population می‌تواند نتیجه رتبه‌بندی را تغییر دهد. هر تغییر از این نوع نیازمند تأیید Business Owner و Regression Test است.
