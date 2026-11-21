# Карточки открытых эпизодов

Сгенерировано `python tools/episode_cards.py` (читает `grader/` **открытых** эпизодов — это и так опубликованный
эталон). Для каждого из 20 эпизодов: откуда он, что в нём заложено и как с ним справляется честный
`simple_reconcile` (режим train). Разбор ошибок «до/после» — `python -m auditenv explain episodes/<split>/<id>`.

| Эпизод | Конфиг#seed | База / иностранные | Пояс | Проводок | Ошибки | simple_reconcile |
|---|---|---|---|---|---|---|
| `train/ep-p2ndc2nyey` | train-easy#101 | KZT / USD | Asia/Almaty (UTC+5:00) | 252 | period_cutoff/prior_period | TP 1 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-wtma6rce3f` | train-easy#102 | KZT / USD | Asia/Almaty (UTC+5:00) | 235 | duplicate_invoice/copy, period_cutoff/prior_period | TP 2 · FP 0 · FN 0 · reward +0.980 · 11 шагов |
| `train/ep-4qgxw85smv` | train-easy#103 | KZT / USD | Asia/Almaty (UTC+5:00) | 274 | — (чистая книга) | TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-rntewpty5c` | train-easy#104 | KZT / USD | Asia/Almaty (UTC+5:00) | 288 | duplicate_invoice/copy, payment_allocation/unallocated | TP 2 · FP 1 · FN 0 · reward +0.578 · 12 шагов |
| `train/ep-rmhcqsyns9` | train-easy#105 | KZT / USD | Asia/Almaty (UTC+5:00) | 296 | period_cutoff/prior_period, period_cutoff/prior_period, period_cutoff/utc_trap | TP 3 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-jpekadpkeb` | train-easy#106 | KZT / USD | Asia/Almaty (UTC+5:00) | 297 | — (чистая книга) | TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-57e8bktrhw` | train-global#107 | USD / JPY, KZT | Pacific/Pago_Pago (UTC-11:00) | 291 | duplicate_invoice/copy, period_cutoff/prior_period, period_cutoff/prior_period | TP 3 · FP 2 · FN 0 · reward +0.474 · 14 шагов |
| `train/ep-mt68p5wbd2` | train-global#108 | USD / JPY, KWD | America/Lima (UTC-5:00) | 290 | duplicate_invoice/copy, payment_allocation/partial, fx_rate/adjacent_day | TP 2 · FP 0 · FN 1 · reward +0.574 · 14 шагов |
| `train/ep-t7w2w69599` | train-global#109 | USD / EUR, JPY | Asia/Kathmandu (UTC+5:45) | 266 | payment_allocation/unallocated, fx_rate/adjacent_day, period_cutoff/prior_period | TP 2 · FP 1 · FN 1 · reward +0.307 · 14 шагов |
| `train/ep-8htn7y36fp` | train-global#110 | USD / KWD, KZT | Pacific/Kiritimati (UTC+14:00) | 280 | fx_rate/adjacent_day | TP 1 · FP 1 · FN 0 · reward +0.311 · 12 шагов |
| `dev/ep-3bwbxj4nsy` | dev-mixed#201 | KZT / JPY, KWD | Asia/Dubai (UTC+4:00) | 307 | fx_rate/adjacent_day | TP 1 · FP 1 · FN 0 · reward +0.305 · 15 шагов |
| `dev/ep-yee4e3r3ar` | dev-mixed#202 | KZT / KWD, USD | Asia/Almaty (UTC+5:00) | 264 | payment_allocation/unallocated | TP 1 · FP 1 · FN 0 · reward +0.307 · 14 шагов |
| `dev/ep-vw9vceq4qf` | dev-mixed#203 | KZT / JPY, KWD | Asia/Almaty (UTC+5:00) | 290 | fx_rate/adjacent_day, payment_allocation/partial | TP 1 · FP 1 · FN 1 · reward -0.026 · 14 шагов |
| `dev/ep-eedmc2zyem` | dev-global#204 | USD / JPY, KWD, KZT | Asia/Tokyo (UTC+9:00) | 295 | — (чистая книга) | TP 0 · FP 0 · FN 0 · reward +0.974 · 14 шагов |
| `dev/ep-ghqjfb86vj` | dev-global#205 | JPY / EUR, USD | Pacific/Pago_Pago (UTC-11:00) | 261 | fx_rate/utc_date, payment_allocation/partial, duplicate_invoice/paid_twice, payment_allocation/unallocated | TP 4 · FP 0 · FN 0 · reward +0.974 · 14 шагов |
| `dev/ep-vq9n3qwk8v` | interaction-heavy#206 | KZT / EUR, KWD, USD | Asia/Dubai (UTC+4:00) | 335 | fx_rate/adjacent_day, duplicate_invoice/copy_as_posted | TP 2 · FP 2 · FN 0 · reward +0.303 · 16 шагов |
| `dev/ep-byttstzrqb` | interaction-heavy#207 | KZT / EUR, USD | America/Lima (UTC-5:00) | 307 | fx_rate/historical_rate, payment_allocation/partial, payment_allocation/unallocated | TP 2 · FP 1 · FN 1 · reward +0.305 · 15 шагов |
| `dev/ep-htfdvq2mvr` | interaction-heavy#208 | KZT / JPY, USD | Asia/Kolkata (UTC+5:30) | 303 | fx_rate/wrong_pair, duplicate_invoice/copy_as_posted, fx_rate/adjacent_day, payment_allocation/partial | TP 3 · FP 2 · FN 1 · reward +0.305 · 15 шагов |
| `dev/ep-ap6e6dpf7p` | clean-only#209 | KZT / EUR, USD | Asia/Almaty (UTC+5:00) | 249 | — (чистая книга) | TP 0 · FP 2 · FN 0 · reward -1.000 · 13 шагов |
| `dev/ep-etjx7zm8qz` | clean-only#210 | KZT / EUR, JPY | Asia/Tokyo (UTC+9:00) | 285 | — (чистая книга) | TP 0 · FP 2 · FN 0 · reward -1.000 · 14 шагов |

## `train/ep-p2ndc2nyey`

* Конфиг `train-easy`, seed 101; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 252 проводок, 35 счетов, 19 платежей, 80 курсов.
* Ошибки: period_cutoff/prior_period.
* Корректные «двойники»: repeat_amount, split_payment, boundary_time, weekend_fx.
* simple_reconcile: TP 1 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-wtma6rce3f`

* Конфиг `train-easy`, seed 102; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 235 проводок, 35 счетов, 19 платежей, 80 курсов.
* Ошибки: duplicate_invoice/copy, period_cutoff/prior_period.
* Корректные «двойники»: repeat_amount, split_payment, boundary_time, weekend_fx.
* simple_reconcile: TP 2 · FP 0 · FN 0 · reward +0.980 · 11 шагов.

## `train/ep-4qgxw85smv`

* Конфиг `train-easy`, seed 103; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 274 проводок, 36 счетов, 20 платежей, 80 курсов.
* Ошибки: нет.
* Корректные «двойники»: repeat_amount, multi_invoice_payment, partial_open, boundary_time, night_fx.
* simple_reconcile: TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-rntewpty5c`

* Конфиг `train-easy`, seed 104; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 288 проводок, 42 счетов, 21 платежей, 81 курсов.
* Ошибки: duplicate_invoice/copy, payment_allocation/unallocated.
* Корректные «двойники»: split_payment, boundary_time, credit_note_reissue, night_fx.
* simple_reconcile: TP 2 · FP 1 · FN 0 · reward +0.578 · 12 шагов.

## `train/ep-rmhcqsyns9`

* Конфиг `train-easy`, seed 105; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 296 проводок, 43 счетов, 21 платежей, 80 курсов.
* Ошибки: period_cutoff/prior_period, period_cutoff/prior_period, period_cutoff/utc_trap.
* Корректные «двойники»: recurring_rent, partial_open, boundary_time, night_fx.
* simple_reconcile: TP 3 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-jpekadpkeb`

* Конфиг `train-easy`, seed 106; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 297 проводок, 38 счетов, 25 платежей, 81 курсов.
* Ошибки: нет.
* Корректные «двойники»: repeat_amount, partial_open, boundary_time, night_fx.
* simple_reconcile: TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-57e8bktrhw`

* Конфиг `train-global`, seed 107; период 2026-02-01 … 2026-05-01; пояс Pacific/Pago_Pago (UTC-11:00).
* Размер: 291 проводок, 39 счетов, 20 платежей, 158 курсов.
* Ошибки: duplicate_invoice/copy, period_cutoff/prior_period, period_cutoff/prior_period.
* Корректные «двойники»: repeat_amount, partial_open, refund, rounding_residual, boundary_time, credit_note_reissue, overpayment.
* simple_reconcile: TP 3 · FP 2 · FN 0 · reward +0.474 · 14 шагов.

## `train/ep-mt68p5wbd2`

* Конфиг `train-global`, seed 108; период 2026-11-01 … 2027-02-01; пояс America/Lima (UTC-5:00).
* Размер: 290 проводок, 40 счетов, 24 платежей, 160 курсов.
* Ошибки: duplicate_invoice/copy, payment_allocation/partial, fx_rate/adjacent_day.
* Корректные «двойники»: recurring_rent, bank_fee, rounding_residual, boundary_time, unidentified_receipt.
* simple_reconcile: TP 2 · FP 0 · FN 1 · reward +0.574 · 14 шагов.

## `train/ep-t7w2w69599`

* Конфиг `train-global`, seed 109; период 2026-11-01 … 2027-02-01; пояс Asia/Kathmandu (UTC+5:45).
* Размер: 266 проводок, 37 счетов, 29 платежей, 160 курсов.
* Ошибки: payment_allocation/unallocated, fx_rate/adjacent_day, period_cutoff/prior_period.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, partial_open, rounding_residual, boundary_time, unidentified_receipt, overpayment, weekend_fx.
* simple_reconcile: TP 2 · FP 1 · FN 1 · reward +0.307 · 14 шагов.

## `train/ep-8htn7y36fp`

* Конфиг `train-global`, seed 110; период 2026-02-01 … 2026-03-01; пояс Pacific/Kiritimati (UTC+14:00).
* Размер: 280 проводок, 37 счетов, 20 платежей, 70 курсов.
* Ошибки: fx_rate/adjacent_day.
* Корректные «двойники»: partial_open, bank_fee, boundary_time, credit_note_reissue, unidentified_receipt, weekend_fx.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.311 · 12 шагов.

## `dev/ep-3bwbxj4nsy`

* Конфиг `dev-mixed`, seed 201; период 2026-07-01 … 2026-10-01; пояс Asia/Dubai (UTC+4:00).
* Размер: 307 проводок, 37 счетов, 24 платежей, 162 курсов.
* Ошибки: fx_rate/adjacent_day.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, overpayment.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.305 · 15 шагов.

## `dev/ep-yee4e3r3ar`

* Конфиг `dev-mixed`, seed 202; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 264 проводок, 35 счетов, 23 платежей, 162 курсов.
* Ошибки: payment_allocation/unallocated.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, bank_fee, boundary_time, unidentified_receipt, overpayment, weekend_fx.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.307 · 14 шагов.

## `dev/ep-vw9vceq4qf`

* Конфиг `dev-mixed`, seed 203; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 290 проводок, 37 счетов, 29 платежей, 160 курсов.
* Ошибки: fx_rate/adjacent_day, payment_allocation/partial; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, unidentified_receipt, overpayment.
* simple_reconcile: TP 1 · FP 1 · FN 1 · reward -0.026 · 14 шагов.

## `dev/ep-eedmc2zyem`

* Конфиг `dev-global`, seed 204; период 2026-11-01 … 2027-01-01; пояс Asia/Tokyo (UTC+9:00).
* Размер: 295 проводок, 40 счетов, 20 платежей, 177 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, bank_fee, boundary_time, night_fx, weekend_fx.
* simple_reconcile: TP 0 · FP 0 · FN 0 · reward +0.974 · 14 шагов.

## `dev/ep-ghqjfb86vj`

* Конфиг `dev-global`, seed 205; период 2026-02-01 … 2026-05-01; пояс Pacific/Pago_Pago (UTC-11:00).
* Размер: 261 проводок, 37 счетов, 23 платежей, 158 курсов.
* Ошибки: fx_rate/utc_date, payment_allocation/partial, duplicate_invoice/paid_twice, payment_allocation/unallocated; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, rounding_residual, boundary_time, unidentified_receipt.
* simple_reconcile: TP 4 · FP 0 · FN 0 · reward +0.974 · 14 шагов.

## `dev/ep-vq9n3qwk8v`

* Конфиг `interaction-heavy`, seed 206; период 2026-07-01 … 2026-10-01; пояс Asia/Dubai (UTC+4:00).
* Размер: 335 проводок, 46 счетов, 26 платежей, 243 курсов.
* Ошибки: fx_rate/adjacent_day, duplicate_invoice/copy_as_posted; сценарии: duplicate_fx.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, refund, bank_fee, boundary_time, unidentified_receipt, night_fx, overpayment, weekend_fx.
* simple_reconcile: TP 2 · FP 2 · FN 0 · reward +0.303 · 16 шагов.

## `dev/ep-byttstzrqb`

* Конфиг `interaction-heavy`, seed 207; период 2026-08-01 … 2026-11-01; пояс America/Lima (UTC-5:00).
* Размер: 307 проводок, 41 счетов, 23 платежей, 160 курсов.
* Ошибки: fx_rate/historical_rate, payment_allocation/partial, payment_allocation/unallocated; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, weekend_fx.
* simple_reconcile: TP 2 · FP 1 · FN 1 · reward +0.305 · 15 шагов.

## `dev/ep-htfdvq2mvr`

* Конфиг `interaction-heavy`, seed 208; период 2026-08-01 … 2026-11-01; пояс Asia/Kolkata (UTC+5:30).
* Размер: 303 проводок, 42 счетов, 29 платежей, 160 курсов.
* Ошибки: fx_rate/wrong_pair, duplicate_invoice/copy_as_posted, fx_rate/adjacent_day, payment_allocation/partial; сценарии: duplicate_fx, partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, partial_open, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, night_fx, overpayment.
* simple_reconcile: TP 3 · FP 2 · FN 1 · reward +0.305 · 15 шагов.

## `dev/ep-ap6e6dpf7p`

* Конфиг `clean-only`, seed 209; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 249 проводок, 35 счетов, 25 платежей, 162 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, boundary_time, credit_note_reissue, unidentified_receipt, overpayment, weekend_fx.
* simple_reconcile: TP 0 · FP 2 · FN 0 · reward -1.000 · 13 шагов.

## `dev/ep-etjx7zm8qz`

* Конфиг `clean-only`, seed 210; период 2026-07-01 … 2026-10-01; пояс Asia/Tokyo (UTC+9:00).
* Размер: 285 проводок, 38 счетов, 26 платежей, 162 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, refund, bank_fee, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, night_fx, overpayment, weekend_fx.
* simple_reconcile: TP 0 · FP 2 · FN 0 · reward -1.000 · 14 шагов.
