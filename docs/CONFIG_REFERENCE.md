# Справочник параметров конфига

Сгенерировано из `schemas/config.schema.json` и `auditenv/config.py::DEFAULT_CONFIG` командой
`python -m auditenv validate-config --write-reference`; тест `tests/test_round4_config.py` сверяет файл со
схемой. Конфиг — JSON с любым подмножеством ключей: недостающие берутся из значений по умолчанию
(вложенные словари сливаются по ключам). Проверить свой файл:

```bash
python -m auditenv validate-config configs/dev-mixed.json
```

Что будет при выходе за диапазон: **конфиг не загрузится** — `load_config` бросает `ConfigError`,
генератор не запускается, а `validate-config` печатает все нарушения сразу с подсказкой и кодом
возврата 1. Неизвестный ключ — тоже ошибка (`additionalProperties: false`), чтобы опечатка не
превращалась в молча проигнорированный параметр.

| Параметр | Тип | Диапазон / значения | По умолчанию | Смысл |
|---|---|---|---|---|
| `name` | string | любое | `"default"` | имя конфига (печатается в ошибках; в manifest не попадает — только хеш) |
| `version` | string | любое | `"1.0"` | версия конфига; смена содержимого без смены версии ловит `configs/LOCK.json` |
| `base_currencies` | array of enum | ≥ 1 элем. `KZT`, `USD`, `EUR`, `JPY`, `KWD` | `["KZT"]` | базовая валюта эпизода выбирается из этого списка |
| `foreign_currencies` | array of enum | `KZT`, `USD`, `EUR`, `JPY`, `KWD` | `["USD", "EUR"]` | иностранные валюты документов (кроме базовой) |
| `n_foreign` | array of integer | [мин, макс] ≥ 0 | `[1, 2]` | сколько иностранных валют в эпизоде [мин, макс] |
| `foreign_share` | number | 0…1 | `0.3` | доля документов в иностранной валюте |
| `timezones` | array of enum | ≥ 1 элем. `Asia/Almaty`, `Asia/Tashkent`, `Asia/Dubai`, `Asia/Kolkata`, `Asia/Tokyo`, `America/Bogota`, `America/Lima`, `Asia/Kathmandu`, `Pacific/Kiritimati`, `Pacific/Pago_Pago` | `["Asia/Almaty", "Asia/Tashkent", "Asia/Dubai", "Asia/Kolk…` | часовой пояс компании (без летнего времени) |
| `period_starts` | array of string | ≥ 1 элем. `^20[0-9]{2}-(0[1-9]\|1[0-2])$` | `["2026-07", "2026-08"]` | месяц начала периода `YYYY-MM` |
| `period_months` | integer или array of integer | 1…6 или [мин, макс] 1…6 | `3` | длина периода в месяцах: число или [мин, макс] |
| `n_entities` | array of integer | [мин, макс] 1…500 | `[8, 14]` | число клиентов [мин, макс] |
| `n_invoices` | array of integer | [мин, макс] 5…2000 | `[26, 36]` | число обычных счетов [мин, макс] (плюс отвлекающие случаи) |
| `line_items` | array of integer | [мин, макс] 1…10 | `[3, 7]` | строк в счёте [мин, макс] |
| `utc_share` | array of integer | [мин, макс] ≥ 0 | `[30, 70]` | процент документов, у которых время записано в UTC, а не в местном смещении [мин, макс] |
| `distractors` | object | ключи: `recurring_rent`, `repeat_amount`, `split_payment`, `multi_invoice_payment`, `partial_open`, `refund`, `bank_fee`, `rounding_residual`, `boundary_time`, `credit_note_reissue`, `unidentified_receipt`, `night_fx`, `overpayment`, `weekend_fx` | `{"recurring_rent": 0.5, "repeat_amount": 0.4, "split_paym…` | вероятность каждого корректного отвлекающего случая |
| `distractors.recurring_rent` | number | 0…1 | `0.5` | |
| `distractors.repeat_amount` | number | 0…1 | `0.4` | |
| `distractors.split_payment` | number | 0…1 | `0.5` | |
| `distractors.multi_invoice_payment` | number | 0…1 | `0.5` | |
| `distractors.partial_open` | number | 0…1 | `0.5` | |
| `distractors.refund` | number | 0…1 | `0.4` | |
| `distractors.bank_fee` | number | 0…1 | `0.5` | |
| `distractors.rounding_residual` | number | 0…1 | `0.4` | |
| `distractors.boundary_time` | number | 0…1 | `0.6` | |
| `distractors.credit_note_reissue` | number | 0…1 | `0.3` | |
| `distractors.unidentified_receipt` | number | 0…1 | `0.3` | |
| `distractors.night_fx` | number | 0…1 | `0.5` | |
| `distractors.overpayment` | number | 0…1 | `0.3` | |
| `distractors.weekend_fx` | number | 0…1 | `0.5` | |
| `clean_probability` | number | 0…1 | `0.2` | вероятность чистого эпизода (эталон пуст) |
| `n_errors` | array of integer | [мин, макс] 0…12 | `[1, 4]` | число ошибок в нечистом эпизоде [мин, макс] |
| `errors` | object | ключи: `duplicate_invoice`, `payment_allocation`, `fx_rate`, `period_cutoff`, `vat_error` | `{"duplicate_invoice": 1.0, "payment_allocation": 1.0, "fx…` | веса пяти типов ошибок (0 — тип выключен) |
| `errors.duplicate_invoice` | number | ≥ 0 | `1.0` | |
| `errors.payment_allocation` | number | ≥ 0 | `1.0` | |
| `errors.fx_rate` | number | ≥ 0 | `1.0` | |
| `errors.period_cutoff` | number | ≥ 0 | `1.0` | |
| `errors.vat_error` | number | ≥ 0 | `1.0` | |
| `interactions` | object | ключи: `partial_fx_cutoff`, `duplicate_fx` | `{"partial_fx_cutoff": 0.0, "duplicate_fx": 0.0}` | вероятность сценариев взаимодействующих ошибок |
| `interactions.partial_fx_cutoff` | number | 0…1 | `0.0` | |
| `interactions.duplicate_fx` | number | 0…1 | `0.0` | |
| `min_interactions` | integer | 0…2 | `0` | сколько сценариев взаимодействия обязательно в нечистом эпизоде |
| `fx_variants` | object | ключи: `adjacent_day`, `utc_date`, `inverted`, `historical_rate`, `wrong_pair`, `due_date` | `{"adjacent_day": 0.35, "utc_date": 0.3, "inverted": 0.05,…` | веса вариантов ошибки fx_rate |
| `fx_variants.adjacent_day` | number | ≥ 0 | `0.35` | |
| `fx_variants.utc_date` | number | ≥ 0 | `0.3` | |
| `fx_variants.inverted` | number | ≥ 0 | `0.05` | |
| `fx_variants.historical_rate` | number | ≥ 0 | `0.15` | |
| `fx_variants.wrong_pair` | number | ≥ 0 | `0.1` | |
| `fx_variants.due_date` | number | ≥ 0 | `0.05` | |
| `allocation_variants` | object | ключи: `unallocated`, `partial`, `wrong_invoice` | `{"unallocated": 0.4, "partial": 0.4, "wrong_invoice": 0.2}` | веса вариантов ошибки payment_allocation |
| `allocation_variants.unallocated` | number | ≥ 0 | `0.4` | |
| `allocation_variants.partial` | number | ≥ 0 | `0.4` | |
| `allocation_variants.wrong_invoice` | number | ≥ 0 | `0.2` | |
| `duplicate_variants` | object | ключи: `copy`, `paid_twice` | `{"copy": 0.7, "paid_twice": 0.3}` | веса вариантов ошибки duplicate_invoice |
| `duplicate_variants.copy` | number | ≥ 0 | `0.7` | |
| `duplicate_variants.paid_twice` | number | ≥ 0 | `0.3` | |
| `cutoff_variants` | object | ключи: `utc_trap`, `backdated_posting`, `prior_period` | `{"utc_trap": 0.6, "backdated_posting": 0.2, "prior_period…` | веса вариантов ошибки period_cutoff |
| `cutoff_variants.utc_trap` | number | ≥ 0 | `0.6` | |
| `cutoff_variants.backdated_posting` | number | ≥ 0 | `0.2` | |
| `cutoff_variants.prior_period` | number | ≥ 0 | `0.2` | |
| `vat_share` | number | 0…1 | `0.35` | share of base-currency invoices with a 'VAT 12%' line |
| `min_lookalikes_per_type` | integer | 0…3 | `1` | минимум корректных «двойников» каждого типа ошибки в эпизоде |
| `max_steps` | const | `100` | `100` | лимит шагов агента (кейс: ровно 100) |
| `tolerance_minor` | integer | 0…49 | `1` | допуск по сумме в минимальных единицах |
| `max_attempts` | integer | 1…200 | `40` | сколько под‑seed перебирать, если сканер совпадений отклонил эпизод |

## Правила между параметрами (проверяются после схемы)

| Где | Нарушение | Сообщение / причина |
|---|---|---|
| `[мин, макс]` | мин > макс | `<key>: min > max` |
| `max_steps` | не 100 | кейс фиксирует 100 шагов |
| `utc_share` | больше 100 | это проценты 0..100 |
| `clean_probability < 1` | `n_errors` = [.., 0] | нечистый эпизод без ошибок невозможен |
| `errors`, `interactions` | все веса 0 при `clean_probability < 1` | нечего вносить |
| только `fx_rate` или только сценарии | нет иностранной валюты | нечего конвертировать неверно |
| `min_interactions` | больше числа включённых сценариев или без иностранной валюты | сценарий не внести |
| `min_interactions` | `2 × min_interactions > n_errors[1]` | каждый сценарий даёт 2 issue |

## Именованные конфиги

| Файл | Версия | Отличия от значений по умолчанию |
|---|---|---|
| `configs/clean-only.json` | 2.3 | `foreign_currencies`, `n_foreign`, `foreign_share`, `timezones`, `n_invoices`, `distractors`, `clean_probability`, `n_errors` |
| `configs/dev-global.json` | 2.3 | `base_currencies`, `foreign_currencies`, `n_foreign`, `foreign_share`, `timezones`, `period_starts`, `period_months`, `n_invoices`, `clean_probability`, `n_errors`, `interactions` |
| `configs/dev-mixed.json` | 2.3 | `base_currencies`, `foreign_currencies`, `n_foreign`, `foreign_share`, `timezones`, `n_invoices`, `distractors`, `clean_probability`, `n_errors`, `interactions` |
| `configs/interaction-heavy.json` | 2.3 | `foreign_currencies`, `n_foreign`, `foreign_share`, `timezones`, `n_invoices`, `distractors`, `clean_probability`, `n_errors`, `interactions`, `min_interactions` |
| `configs/stress.json` | 2.3 | `foreign_currencies`, `n_foreign`, `period_months`, `period_starts`, `n_entities`, `n_invoices`, `clean_probability`, `n_errors`, `interactions` |
| `configs/train-easy.json` | 2.3 | `foreign_currencies`, `n_foreign`, `foreign_share`, `timezones`, `n_invoices`, `distractors`, `clean_probability`, `n_errors`, `errors`, `interactions`, `fx_variants`, `allocation_variants`, `cutoff_variants`, `duplicate_variants` |
| `configs/train-global.json` | 2.3 | `base_currencies`, `foreign_currencies`, `n_foreign`, `foreign_share`, `timezones`, `period_starts`, `period_months`, `n_invoices`, `clean_probability`, `n_errors`, `interactions` |
