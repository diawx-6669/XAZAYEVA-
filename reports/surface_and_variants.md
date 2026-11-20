## Поверхностные признаки (300 эпизодов, документы = счета и платежи)

Признак «отделяет» ошибки, если и precision, и recall > 0.6. Столбцы: P/R по всем ошибкам и лучший P/R по отдельному типу.

| Признак | P (все) | R (все) | худший тип | P | R | ярлык? |
|---|---|---|---|---|---|---|
| paid | 0.01 | 0.52 | payment_allocation | 0.01 | 1.00 | нет |
| night | 0.05 | 0.12 | fx_rate | 0.03 | 0.19 | нет |
| utc_format | 0.02 | 0.58 | fx_rate | 0.01 | 0.64 | нет |
| service_period_ne_issue_month | 0.08 | 0.07 | period_cutoff | 0.07 | 0.39 | нет |
| rent_text | 0.00 | 0.00 | duplicate_invoice | 0.00 | 0.01 | нет |
| single_payment | 0.01 | 0.50 | payment_allocation | 0.01 | 0.98 | нет |
| odd_id_prefix | 0.00 | 0.00 | duplicate_invoice | 0.00 | 0.00 | нет |
| weekend | 0.02 | 0.32 | fx_rate | 0.01 | 0.38 | нет |
| last_3_days | 0.05 | 0.20 | payment_allocation | 0.03 | 0.45 | нет |
| foreign_currency | 0.04 | 0.65 | fx_rate | 0.02 | 1.00 | нет |

## Типы и варианты (300 эпизодов): частота и полнота simple_reconcile

| Тип / вариант | Встречается | Найдено simple_reconcile | Recall |
|---|---|---|---|
| duplicate_invoice / copy | 84 | 84 | 100% |
| duplicate_invoice / copy_as_posted | 57 | 57 | 100% |
| duplicate_invoice / paid_twice | 13 | 13 | 100% |
| fx_rate / adjacent_day | 119 | 63 | 53% |
| fx_rate / due_date | 11 | 8 | 73% |
| fx_rate / historical_rate | 12 | 4 | 33% |
| fx_rate / inverted | 11 | 11 | 100% |
| fx_rate / utc_date | 32 | 31 | 97% |
| fx_rate / wrong_pair | 23 | 13 | 57% |
| payment_allocation / partial | 115 | 115 | 100% |
| payment_allocation / unallocated | 43 | 43 | 100% |
| payment_allocation / wrong_invoice | 5 | 0 | 0% |
| period_cutoff / backdated_posting | 8 | 8 | 100% |
| period_cutoff / prior_period | 40 | 40 | 100% |
| period_cutoff / utc_trap | 31 | 31 | 100% |
| **итого** | **604** | **521** | **86%** |
