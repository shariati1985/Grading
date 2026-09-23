# Canonical Data Contract

## 1. Purpose
This contract defines the minimum branch-level input dataset required by the grading and sensitivity-analysis engine. Bank IT may supply the data through SQL Server, a database view, API/ESB, or another approved integration mechanism, but the adapter presented to the application must return this canonical schema without changing business semantics.

## 2. Canonical input schema

| Field | Persian meaning | Logical type | Required | Current engine/repository rule |
|---|---|---:|---:|---|
| `branch_id` | کد شعبه | string | Yes | Non-blank and unique. Leading zeros must be preserved. |
| `branch_name` | نام شعبه | string | Yes | Non-blank. Persian/Arabic character variants and whitespace are normalized by the Excel adapter. |
| `region` | منطقه | string | Yes | Text value; current Excel adapter normalizes Persian/Arabic characters and whitespace. |
| `avg_deposits` | میانگین سپرده‌ها | numeric | Yes | Numeric. Current Excel adapter converts non-numeric/blank input to 0. |
| `deposit_count` | تعداد سپرده‌ها | numeric | Yes | Numeric. Registry minimum is 0 for scenario validation. |
| `avg_loans` | میانگین تسهیلات | numeric | Yes | Numeric. Registry minimum is 0 for scenario validation. |
| `loan_count` | تعداد تسهیلات | numeric | Yes | Numeric. Registry minimum is 0 for scenario validation. |
| `avg_commitments` | میانگین تعهدات | numeric | Yes | Numeric. Registry minimum is 0 for scenario validation. |
| `commitment_count` | تعداد تعهدات | numeric | Yes | Numeric. Registry minimum is 0 for scenario validation. |
| `transaction_volume` | حجم عملیات | numeric | Yes | Numeric. Registry minimum is 0 for scenario validation. |
| `profit_loss` | سود (زیان) | numeric | Yes | Numeric; negative values are allowed. |

The canonical field order is:

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

## 3. Source-to-canonical mapping used by the current Excel prototype

| Current Persian source column | Canonical field |
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

Rows whose branch name is equivalent to `اوزان`, `وزن`, `weight`, or `weights` are excluded by the current Excel adapter and must not be emitted as branch rows by a production source.

## 4. Identity and uniqueness rules
- `branch_id` is the application-level branch key.
- It must be supplied as text or converted losslessly to text.
- Leading zeros are significant and must not be discarded.
- Blank `branch_id` values are rejected.
- Duplicate `branch_id` values are rejected for one loaded baseline population.
- Blank `branch_name` values are rejected.

## 5. Numeric handling
The current Excel adapter:
1. normalizes Persian/Arabic digits to English digits;
2. removes common thousands separators;
3. normalizes minus-sign variants;
4. attempts numeric conversion;
5. converts blank/non-numeric values to `0.0`.

The core ranking engine also converts non-numeric indicator values to numeric and fills conversion failures with `0.0`.

This is the **current implemented behavior**, not a recommendation that production source systems silently replace invalid data with zero. For production integration, data-quality errors should preferably be identified upstream and reported before the canonical dataset reaches the engine. Any decision to change the current zero-fill semantics must be treated as a business-rule change and regression-tested.

## 6. Indicator direction and current official weights

| Indicator | Direction | Weight |
|---|---|---:|
| `avg_deposits` | benefit | 0.500 |
| `deposit_count` | benefit | 0.005 |
| `avg_loans` | benefit | 0.260 |
| `loan_count` | benefit | 0.010 |
| `avg_commitments` | benefit | 0.170 |
| `commitment_count` | benefit | 0.010 |
| `transaction_volume` | benefit | 0.015 |
| `profit_loss` | benefit | 0.030 |

The weights sum to 1.0. The production integration layer must provide raw indicator values only; it must not pre-normalize or re-weight them unless a formally approved model change is introduced.

## 7. Period
The current prototype has one configured baseline period. The runtime exposes `BASE_PERIOD` as an external configuration value.

The existing canonical input dataframe does **not** contain a `period_id` column. The period is currently supplied separately to the repository/runtime contract. If Bank IT requires multi-period storage, the source implementation may store period information internally, but each call to `load_branch_data(period)` must return the single requested branch population in the canonical schema above.

## 8. Output contracts exposed by the model/dashboard layer

### Branch summary
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

### Branch-indicator detail
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

### Indicator definitions
```text
indicator_id
indicator_name
weight
direction
```

### Period list
```text
period_id
period_label
```

The dashboard repository exposes engine results; it does not recalculate model values independently.

## 9. Acceptance checks for the production data adapter
Before UAT, Bank IT should demonstrate that:
- all 11 canonical columns are returned;
- no branch has a blank or duplicate `branch_id`;
- leading-zero branch identifiers are preserved;
- branch names are non-blank;
- all eight indicator fields are numeric at the application boundary;
- the requested period returns the intended population;
- the same approved baseline dataset produces the same model results as the handover baseline;
- source adapters do not calculate their own normalized score, rank, grade, or weighted score.

## 10. Change control
Changing field meaning, aggregation basis, units, period semantics, null handling, indicator direction, weights, or population rules can alter ranking results. Such changes require explicit business-owner approval and regression testing.
