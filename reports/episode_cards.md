# Карточки открытых эпизодов

Сгенерировано `python tools/episode_cards.py` (читает `grader/` **открытых** эпизодов — это и так опубликованный
эталон). Для каждого из 20 эпизодов: откуда он, что в нём заложено и как с ним справляется честный
`simple_reconcile` (режим train). Разбор ошибок «до/после» — `python -m auditenv explain episodes/<split>/<id>`.

| Эпизод | Конфиг#seed | База / иностранные | Пояс | Проводок | Ошибки | simple_reconcile |
|---|---|---|---|---|---|---|
| `train/ep-hg7nbxf7rj` | train-easy#101 | KZT / USD | Asia/Almaty (UTC+5:00) | 245 | period_cutoff/prior_period | TP 1 · FP 0 · FN 0 · reward +0.980 · 11 шагов |
| `train/ep-qmagfmdtgk` | train-easy#102 | KZT / USD | Asia/Almaty (UTC+5:00) | 235 | duplicate_invoice/copy, period_cutoff/utc_trap | TP 2 · FP 0 · FN 0 · reward +0.980 · 11 шагов |
| `train/ep-yaax7jrr8c` | train-easy#103 | KZT / USD | Asia/Almaty (UTC+5:00) | 273 | — (чистая книга) | TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-axybv5w3gj` | train-easy#104 | KZT / USD | Asia/Almaty (UTC+5:00) | 284 | duplicate_invoice/copy, payment_allocation/unallocated | TP 2 · FP 1 · FN 0 · reward +0.578 · 12 шагов |
| `train/ep-8jyef897pe` | train-easy#105 | KZT / USD | Asia/Almaty (UTC+5:00) | 302 | period_cutoff/prior_period, period_cutoff/utc_trap, period_cutoff/prior_period | TP 3 · FP 0 · FN 0 · reward +0.976 · 13 шагов |
| `train/ep-d5c3xcajzd` | train-easy#106 | KZT / USD | Asia/Almaty (UTC+5:00) | 299 | — (чистая книга) | TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-3yf7k4tcbn` | train-global#107 | USD / JPY, KZT | Pacific/Pago_Pago (UTC-11:00) | 292 | duplicate_invoice/copy, period_cutoff/prior_period, period_cutoff/prior_period | TP 3 · FP 2 · FN 0 · reward +0.474 · 14 шагов |
| `train/ep-kcjvzycstz` | train-global#108 | USD / JPY, KWD | America/Lima (UTC-5:00) | 287 | duplicate_invoice/copy, payment_allocation/partial, fx_rate/adjacent_day | TP 3 · FP 0 · FN 0 · reward +0.974 · 14 шагов |
| `train/ep-3q38qq6zcm` | train-global#109 | USD / EUR, JPY | Asia/Kathmandu (UTC+5:45) | 267 | payment_allocation/unallocated, fx_rate/adjacent_day, period_cutoff/prior_period | TP 2 · FP 1 · FN 1 · reward +0.307 · 14 шагов |
| `train/ep-t4cyear95j` | train-global#110 | USD / KWD, KZT | Pacific/Kiritimati (UTC+14:00) | 277 | fx_rate/adjacent_day | TP 1 · FP 1 · FN 0 · reward +0.311 · 12 шагов |
| `dev/ep-4e8gzahap8` | dev-mixed#201 | KZT / JPY, KWD | Asia/Dubai (UTC+4:00) | 303 | fx_rate/adjacent_day | TP 1 · FP 1 · FN 0 · reward +0.305 · 15 шагов |
| `dev/ep-a7ak5ae4sh` | dev-mixed#202 | KZT / KWD, USD | Asia/Almaty (UTC+5:00) | 272 | payment_allocation/unallocated | TP 1 · FP 1 · FN 0 · reward +0.307 · 14 шагов |
| `dev/ep-83ty6jrf5c` | dev-mixed#203 | KZT / JPY, KWD | Asia/Almaty (UTC+5:00) | 280 | fx_rate/adjacent_day, payment_allocation/partial | TP 1 · FP 1 · FN 1 · reward -0.026 · 14 шагов |
| `dev/ep-9m7sfznpsr` | dev-global#204 | USD / JPY, KWD, KZT | Asia/Tokyo (UTC+9:00) | 318 | — (чистая книга) | TP 0 · FP 0 · FN 0 · reward +0.972 · 15 шагов |
| `dev/ep-n5y6es2vx3` | dev-global#205 | JPY / EUR, USD | Pacific/Pago_Pago (UTC-11:00) | 258 | fx_rate/utc_date, payment_allocation/partial, duplicate_invoice/paid_twice, payment_allocation/unallocated | TP 4 · FP 0 · FN 0 · reward +0.974 · 14 шагов |
| `dev/ep-pdawh48ngm` | interaction-heavy#206 | KZT / EUR, KWD, USD | Asia/Dubai (UTC+4:00) | 360 | fx_rate/adjacent_day, duplicate_invoice/copy_as_posted | TP 1 · FP 1 · FN 1 · reward -0.032 · 17 шагов |
| `dev/ep-5xxfm3xez4` | interaction-heavy#207 | KZT / EUR, USD | America/Lima (UTC-5:00) | 311 | fx_rate/historical_rate, payment_allocation/partial, payment_allocation/unallocated | TP 2 · FP 1 · FN 1 · reward +0.305 · 15 шагов |
| `dev/ep-cc3nbrbwgh` | interaction-heavy#208 | KZT / JPY, USD | Asia/Kolkata (UTC+5:30) | 319 | fx_rate/wrong_pair, duplicate_invoice/copy_as_posted, fx_rate/adjacent_day, payment_allocation/partial | TP 2 · FP 3 · FN 2 · reward -0.139 · 15 шагов |
| `dev/ep-wz2abaewnk` | clean-only#209 | KZT / EUR, USD | Asia/Almaty (UTC+5:00) | 249 | — (чистая книга) | TP 0 · FP 2 · FN 0 · reward -1.000 · 13 шагов |
| `dev/ep-brv9hvpn2r` | clean-only#210 | KZT / EUR, JPY | Asia/Tokyo (UTC+9:00) | 303 | — (чистая книга) | TP 0 · FP 2 · FN 0 · reward -1.000 · 15 шагов |

## `train/ep-hg7nbxf7rj`

* Конфиг `train-easy`, seed 101; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 245 проводок, 35 счетов, 15 платежей, 80 курсов.
* Ошибки: period_cutoff/prior_period.
* Корректные «двойники»: repeat_amount, split_payment, boundary_time, weekend_fx.
* simple_reconcile: TP 1 · FP 0 · FN 0 · reward +0.980 · 11 шагов.

## `train/ep-qmagfmdtgk`

* Конфиг `train-easy`, seed 102; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 235 проводок, 35 счетов, 18 платежей, 80 курсов.
* Ошибки: duplicate_invoice/copy, period_cutoff/utc_trap.
* Корректные «двойники»: repeat_amount, split_payment, boundary_time, weekend_fx.
* simple_reconcile: TP 2 · FP 0 · FN 0 · reward +0.980 · 11 шагов.

## `train/ep-yaax7jrr8c`

* Конфиг `train-easy`, seed 103; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 273 проводок, 36 счетов, 21 платежей, 80 курсов.
* Ошибки: нет.
* Корректные «двойники»: repeat_amount, multi_invoice_payment, partial_open, boundary_time, night_fx.
* simple_reconcile: TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-axybv5w3gj`

* Конфиг `train-easy`, seed 104; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 284 проводок, 42 счетов, 21 платежей, 81 курсов.
* Ошибки: duplicate_invoice/copy, payment_allocation/unallocated.
* Корректные «двойники»: split_payment, boundary_time, credit_note_reissue, night_fx.
* simple_reconcile: TP 2 · FP 1 · FN 0 · reward +0.578 · 12 шагов.

## `train/ep-8jyef897pe`

* Конфиг `train-easy`, seed 105; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 302 проводок, 43 счетов, 24 платежей, 80 курсов.
* Ошибки: period_cutoff/prior_period, period_cutoff/utc_trap, period_cutoff/prior_period.
* Корректные «двойники»: recurring_rent, partial_open, boundary_time, night_fx.
* simple_reconcile: TP 3 · FP 0 · FN 0 · reward +0.976 · 13 шагов.

## `train/ep-d5c3xcajzd`

* Конфиг `train-easy`, seed 106; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 299 проводок, 38 счетов, 25 платежей, 81 курсов.
* Ошибки: нет.
* Корректные «двойники»: repeat_amount, partial_open, boundary_time, night_fx.
* simple_reconcile: TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-3yf7k4tcbn`

* Конфиг `train-global`, seed 107; период 2026-02-01 … 2026-05-01; пояс Pacific/Pago_Pago (UTC-11:00).
* Размер: 292 проводок, 39 счетов, 20 платежей, 158 курсов.
* Ошибки: duplicate_invoice/copy, period_cutoff/prior_period, period_cutoff/prior_period.
* Корректные «двойники»: repeat_amount, partial_open, refund, rounding_residual, boundary_time, credit_note_reissue, overpayment.
* simple_reconcile: TP 3 · FP 2 · FN 0 · reward +0.474 · 14 шагов.

## `train/ep-kcjvzycstz`

* Конфиг `train-global`, seed 108; период 2026-11-01 … 2027-02-01; пояс America/Lima (UTC-5:00).
* Размер: 287 проводок, 40 счетов, 22 платежей, 160 курсов.
* Ошибки: duplicate_invoice/copy, payment_allocation/partial, fx_rate/adjacent_day.
* Корректные «двойники»: recurring_rent, bank_fee, rounding_residual, boundary_time, unidentified_receipt.
* simple_reconcile: TP 3 · FP 0 · FN 0 · reward +0.974 · 14 шагов.

## `train/ep-3q38qq6zcm`

* Конфиг `train-global`, seed 109; период 2026-11-01 … 2027-02-01; пояс Asia/Kathmandu (UTC+5:45).
* Размер: 267 проводок, 37 счетов, 29 платежей, 160 курсов.
* Ошибки: payment_allocation/unallocated, fx_rate/adjacent_day, period_cutoff/prior_period.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, partial_open, rounding_residual, boundary_time, unidentified_receipt, overpayment, weekend_fx.
* simple_reconcile: TP 2 · FP 1 · FN 1 · reward +0.307 · 14 шагов.

## `train/ep-t4cyear95j`

* Конфиг `train-global`, seed 110; период 2026-02-01 … 2026-03-01; пояс Pacific/Kiritimati (UTC+14:00).
* Размер: 277 проводок, 37 счетов, 20 платежей, 70 курсов.
* Ошибки: fx_rate/adjacent_day.
* Корректные «двойники»: partial_open, bank_fee, boundary_time, credit_note_reissue, unidentified_receipt, weekend_fx.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.311 · 12 шагов.

## `dev/ep-4e8gzahap8`

* Конфиг `dev-mixed`, seed 201; период 2026-07-01 … 2026-10-01; пояс Asia/Dubai (UTC+4:00).
* Размер: 303 проводок, 37 счетов, 24 платежей, 162 курсов.
* Ошибки: fx_rate/adjacent_day.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, overpayment.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.305 · 15 шагов.

## `dev/ep-a7ak5ae4sh`

* Конфиг `dev-mixed`, seed 202; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 272 проводок, 35 счетов, 22 платежей, 162 курсов.
* Ошибки: payment_allocation/unallocated.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, bank_fee, boundary_time, unidentified_receipt, overpayment, weekend_fx.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.307 · 14 шагов.

## `dev/ep-83ty6jrf5c`

* Конфиг `dev-mixed`, seed 203; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 280 проводок, 37 счетов, 28 платежей, 160 курсов.
* Ошибки: fx_rate/adjacent_day, payment_allocation/partial; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, unidentified_receipt, overpayment.
* simple_reconcile: TP 1 · FP 1 · FN 1 · reward -0.026 · 14 шагов.

## `dev/ep-9m7sfznpsr`

* Конфиг `dev-global`, seed 204; период 2026-11-01 … 2027-01-01; пояс Asia/Tokyo (UTC+9:00).
* Размер: 318 проводок, 40 счетов, 25 платежей, 177 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, bank_fee, boundary_time, night_fx, weekend_fx.
* simple_reconcile: TP 0 · FP 0 · FN 0 · reward +0.972 · 15 шагов.

## `dev/ep-n5y6es2vx3`

* Конфиг `dev-global`, seed 205; период 2026-02-01 … 2026-05-01; пояс Pacific/Pago_Pago (UTC-11:00).
* Размер: 258 проводок, 37 счетов, 20 платежей, 158 курсов.
* Ошибки: fx_rate/utc_date, payment_allocation/partial, duplicate_invoice/paid_twice, payment_allocation/unallocated; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, rounding_residual, boundary_time, unidentified_receipt.
* simple_reconcile: TP 4 · FP 0 · FN 0 · reward +0.974 · 14 шагов.

## `dev/ep-pdawh48ngm`

* Конфиг `interaction-heavy`, seed 206; период 2026-07-01 … 2026-10-01; пояс Asia/Dubai (UTC+4:00).
* Размер: 360 проводок, 47 счетов, 30 платежей, 243 курсов.
* Ошибки: fx_rate/adjacent_day, duplicate_invoice/copy_as_posted; сценарии: duplicate_fx.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, refund, bank_fee, boundary_time, unidentified_receipt, night_fx, overpayment, weekend_fx.
* simple_reconcile: TP 1 · FP 1 · FN 1 · reward -0.032 · 17 шагов.

## `dev/ep-5xxfm3xez4`

* Конфиг `interaction-heavy`, seed 207; период 2026-08-01 … 2026-11-01; пояс America/Lima (UTC-5:00).
* Размер: 311 проводок, 41 счетов, 23 платежей, 160 курсов.
* Ошибки: fx_rate/historical_rate, payment_allocation/partial, payment_allocation/unallocated; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, weekend_fx.
* simple_reconcile: TP 2 · FP 1 · FN 1 · reward +0.305 · 15 шагов.

## `dev/ep-cc3nbrbwgh`

* Конфиг `interaction-heavy`, seed 208; период 2026-08-01 … 2026-11-01; пояс Asia/Kolkata (UTC+5:30).
* Размер: 319 проводок, 42 счетов, 31 платежей, 160 курсов.
* Ошибки: fx_rate/wrong_pair, duplicate_invoice/copy_as_posted, fx_rate/adjacent_day, payment_allocation/partial; сценарии: duplicate_fx, partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, partial_open, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, night_fx, overpayment.
* simple_reconcile: TP 2 · FP 3 · FN 2 · reward -0.139 · 15 шагов.

## `dev/ep-wz2abaewnk`

* Конфиг `clean-only`, seed 209; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 249 проводок, 35 счетов, 23 платежей, 162 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, boundary_time, credit_note_reissue, unidentified_receipt, overpayment, weekend_fx.
* simple_reconcile: TP 0 · FP 2 · FN 0 · reward -1.000 · 13 шагов.

## `dev/ep-brv9hvpn2r`

* Конфиг `clean-only`, seed 210; период 2026-07-01 … 2026-10-01; пояс Asia/Tokyo (UTC+9:00).
* Размер: 303 проводок, 37 счетов, 28 платежей, 162 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, refund, bank_fee, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, night_fx, overpayment, weekend_fx.
* simple_reconcile: TP 0 · FP 2 · FN 0 · reward -1.000 · 15 шагов.
