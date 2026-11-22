# Карточки открытых эпизодов

Сгенерировано `python tools/episode_cards.py` (читает `grader/` **открытых** эпизодов — это и так опубликованный
эталон). Для каждого из 20 эпизодов: откуда он, что в нём заложено и как с ним справляется честный
`simple_reconcile` (режим train). Разбор ошибок «до/после» — `python -m auditenv explain episodes/<split>/<id>`.

| Эпизод | Конфиг#seed | База / иностранные | Пояс | Проводок | Ошибки | simple_reconcile |
|---|---|---|---|---|---|---|
| `train/ep-gg65pgfr3w` | train-easy#101 | KZT / USD | Asia/Almaty (UTC+5:00) | 318 | vat_error/paid_in_full_rate_20 | TP 1 · FP 0 · FN 0 · reward +0.976 · 13 шагов |
| `train/ep-j2mnqc5h54` | train-easy#102 | KZT / USD | Asia/Almaty (UTC+5:00) | 283 | duplicate_invoice/copy, vat_error/paid_in_full_rate_20 | TP 2 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-dpppa4qbj5` | train-easy#103 | KZT / USD | Asia/Almaty (UTC+5:00) | 273 | — (чистая книга) | TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-kcj4hkgrcj` | train-easy#104 | KZT / USD | Asia/Almaty (UTC+5:00) | 286 | duplicate_invoice/copy, payment_allocation/unallocated | TP 2 · FP 0 · FN 0 · reward +0.978 · 12 шагов |
| `train/ep-6sbtnqcp2q` | train-easy#105 | KZT / USD | Asia/Almaty (UTC+5:00) | 306 | period_cutoff/utc_trap, period_cutoff/utc_trap, period_cutoff/utc_trap | TP 3 · FP 1 · FN 0 · reward +0.690 · 13 шагов |
| `train/ep-hqe7j35es4` | train-easy#106 | KZT / USD | Asia/Almaty (UTC+5:00) | 327 | — (чистая книга) | TP 0 · FP 1 · FN 0 · reward -1.000 · 13 шагов |
| `train/ep-ak4s2vjfjr` | train-global#107 | USD / JPY, KZT | Pacific/Pago_Pago (UTC-11:00) | 257 | fx_rate/adjacent_day, vat_error/unpaid_rate_20, vat_error/paid_in_full_rate_20 | TP 2 · FP 2 · FN 1 · reward +0.119 · 13 шагов |
| `train/ep-ffb6gxg222` | train-global#108 | USD / JPY, KWD | America/Lima (UTC-5:00) | 294 | duplicate_invoice/copy, fx_rate/adjacent_day, period_cutoff/prior_period | TP 2 · FP 1 · FN 1 · reward +0.309 · 13 шагов |
| `train/ep-8prp3nnn34` | train-global#109 | USD / EUR, JPY | Asia/Kathmandu (UTC+5:45) | 291 | payment_allocation/unallocated, fx_rate/adjacent_day, vat_error/unpaid_rate_10 | TP 2 · FP 0 · FN 1 · reward +0.576 · 13 шагов |
| `train/ep-m6mpctf996` | train-global#110 | USD / KWD, KZT | Pacific/Kiritimati (UTC+14:00) | 304 | fx_rate/adjacent_day | TP 1 · FP 1 · FN 0 · reward +0.309 · 13 шагов |
| `dev/ep-ta6bbcpyts` | dev-mixed#201 | KZT / JPY, KWD | Asia/Dubai (UTC+4:00) | 311 | fx_rate/adjacent_day | TP 0 · FP 1 · FN 1 · reward -1.000 · 15 шагов |
| `dev/ep-vhywwrgxx2` | dev-mixed#202 | KZT / KWD, USD | Asia/Almaty (UTC+5:00) | 310 | payment_allocation/unallocated | TP 1 · FP 1 · FN 0 · reward +0.305 · 15 шагов |
| `dev/ep-xt9h93jnn2` | dev-mixed#203 | KZT / JPY, KWD | Asia/Almaty (UTC+5:00) | 291 | fx_rate/adjacent_day, payment_allocation/partial | TP 1 · FP 0 · FN 1 · reward +0.307 · 14 шагов |
| `dev/ep-nge3f44dyd` | dev-global#204 | USD / JPY, KWD, KZT | Asia/Tokyo (UTC+9:00) | 378 | — (чистая книга) | TP 0 · FP 1 · FN 0 · reward -1.000 · 16 шагов |
| `dev/ep-4qcfb8dahb` | dev-global#205 | JPY / EUR, USD | Pacific/Pago_Pago (UTC-11:00) | 317 | fx_rate/adjacent_day, payment_allocation/partial, payment_allocation/partial, period_cutoff/backdated_posting | TP 4 · FP 1 · FN 0 · reward +0.752 · 14 шагов |
| `dev/ep-wm5bxcrh9d` | interaction-heavy#206 | KZT / EUR, KWD, USD | Asia/Dubai (UTC+4:00) | 294 | fx_rate/adjacent_day, duplicate_invoice/copy_as_posted | TP 2 · FP 1 · FN 0 · reward +0.572 · 15 шагов |
| `dev/ep-vbg7s7cfhm` | interaction-heavy#207 | KZT / EUR, USD | America/Lima (UTC-5:00) | 294 | fx_rate/historical_rate, payment_allocation/partial, payment_allocation/unallocated | TP 2 · FP 0 · FN 1 · reward +0.574 · 14 шагов |
| `dev/ep-vk7pc3rd7r` | interaction-heavy#208 | KZT / JPY, USD | Asia/Kolkata (UTC+5:30) | 319 | fx_rate/wrong_pair, duplicate_invoice/copy_as_posted, fx_rate/adjacent_day, payment_allocation/partial | TP 2 · FP 1 · FN 2 · reward +0.115 · 15 шагов |
| `dev/ep-md93e84dvw` | clean-only#209 | KZT / EUR, USD | Asia/Almaty (UTC+5:00) | 318 | — (чистая книга) | TP 0 · FP 1 · FN 0 · reward -1.000 · 15 шагов |
| `dev/ep-3j67p4jary` | clean-only#210 | KZT / EUR, JPY | Asia/Tokyo (UTC+9:00) | 330 | — (чистая книга) | TP 0 · FP 2 · FN 0 · reward -1.000 · 15 шагов |

## `train/ep-gg65pgfr3w`

* Конфиг `train-easy`, seed 101; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 318 проводок, 41 счетов, 24 платежей, 78 курсов.
* Ошибки: vat_error/paid_in_full_rate_20.
* Корректные «двойники»: repeat_amount, split_payment, multi_invoice_payment, bank_fee, boundary_time, night_fx.
* simple_reconcile: TP 1 · FP 0 · FN 0 · reward +0.976 · 13 шагов.

## `train/ep-j2mnqc5h54`

* Конфиг `train-easy`, seed 102; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 283 проводок, 39 счетов, 27 платежей, 78 курсов.
* Ошибки: duplicate_invoice/copy, vat_error/paid_in_full_rate_20.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, boundary_time, night_fx.
* simple_reconcile: TP 2 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-dpppa4qbj5`

* Конфиг `train-easy`, seed 103; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 273 проводок, 36 счетов, 16 платежей, 78 курсов.
* Ошибки: нет.
* Корректные «двойники»: repeat_amount, multi_invoice_payment, boundary_time, unidentified_receipt, weekend_fx.
* simple_reconcile: TP 0 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-kcj4hkgrcj`

* Конфиг `train-easy`, seed 104; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 286 проводок, 38 счетов, 21 платежей, 79 курсов.
* Ошибки: duplicate_invoice/copy, payment_allocation/unallocated.
* Корректные «двойники»: recurring_rent, split_payment, multi_invoice_payment, partial_open, refund, boundary_time, night_fx.
* simple_reconcile: TP 2 · FP 0 · FN 0 · reward +0.978 · 12 шагов.

## `train/ep-6sbtnqcp2q`

* Конфиг `train-easy`, seed 105; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 306 проводок, 41 счетов, 24 платежей, 78 курсов.
* Ошибки: period_cutoff/utc_trap, period_cutoff/utc_trap, period_cutoff/utc_trap.
* Корректные «двойники»: recurring_rent, refund, boundary_time, night_fx, overpayment.
* simple_reconcile: TP 3 · FP 1 · FN 0 · reward +0.690 · 13 шагов.

## `train/ep-hqe7j35es4`

* Конфиг `train-easy`, seed 106; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 327 проводок, 38 счетов, 25 платежей, 79 курсов.
* Ошибки: нет.
* Корректные «двойники»: repeat_amount, multi_invoice_payment, refund, bank_fee, boundary_time, night_fx, overpayment, weekend_fx.
* simple_reconcile: TP 0 · FP 1 · FN 0 · reward -1.000 · 13 шагов.

## `train/ep-ak4s2vjfjr`

* Конфиг `train-global`, seed 107; период 2026-02-01 … 2026-05-01; пояс Pacific/Pago_Pago (UTC-11:00).
* Размер: 257 проводок, 33 счетов, 20 платежей, 150 курсов.
* Ошибки: fx_rate/adjacent_day, vat_error/unpaid_rate_20, vat_error/paid_in_full_rate_20.
* Корректные «двойники»: split_payment, multi_invoice_payment, partial_open, refund, boundary_time, credit_note_reissue, night_fx, overpayment.
* simple_reconcile: TP 2 · FP 2 · FN 1 · reward +0.119 · 13 шагов.

## `train/ep-ffb6gxg222`

* Конфиг `train-global`, seed 108; период 2026-11-01 … 2027-02-01; пояс America/Lima (UTC-5:00).
* Размер: 294 проводок, 37 счетов, 25 платежей, 150 курсов.
* Ошибки: duplicate_invoice/copy, fx_rate/adjacent_day, period_cutoff/prior_period.
* Корректные «двойники»: repeat_amount, split_payment, partial_open, boundary_time, credit_note_reissue, night_fx.
* simple_reconcile: TP 2 · FP 1 · FN 1 · reward +0.309 · 13 шагов.

## `train/ep-8prp3nnn34`

* Конфиг `train-global`, seed 109; период 2026-11-01 … 2027-02-01; пояс Asia/Kathmandu (UTC+5:45).
* Размер: 291 проводок, 41 счетов, 25 платежей, 150 курсов.
* Ошибки: payment_allocation/unallocated, fx_rate/adjacent_day, vat_error/unpaid_rate_10.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, partial_open, boundary_time, unidentified_receipt, night_fx.
* simple_reconcile: TP 2 · FP 0 · FN 1 · reward +0.576 · 13 шагов.

## `train/ep-m6mpctf996`

* Конфиг `train-global`, seed 110; период 2026-02-01 … 2026-03-01; пояс Pacific/Kiritimati (UTC+14:00).
* Размер: 304 проводок, 37 счетов, 23 платежей, 70 курсов.
* Ошибки: fx_rate/adjacent_day.
* Корректные «двойники»: partial_open, bank_fee, boundary_time, credit_note_reissue, unidentified_receipt, weekend_fx.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.309 · 13 шагов.

## `dev/ep-ta6bbcpyts`

* Конфиг `dev-mixed`, seed 201; период 2026-07-01 … 2026-10-01; пояс Asia/Dubai (UTC+4:00).
* Размер: 311 проводок, 39 счетов, 21 платежей, 158 курсов.
* Ошибки: fx_rate/adjacent_day.
* Корректные «двойники»: repeat_amount, split_payment, multi_invoice_payment, boundary_time, credit_note_reissue, night_fx.
* simple_reconcile: TP 0 · FP 1 · FN 1 · reward -1.000 · 15 шагов.

## `dev/ep-vhywwrgxx2`

* Конфиг `dev-mixed`, seed 202; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 310 проводок, 42 счетов, 27 платежей, 158 курсов.
* Ошибки: payment_allocation/unallocated.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, boundary_time, night_fx, overpayment.
* simple_reconcile: TP 1 · FP 1 · FN 0 · reward +0.305 · 15 шагов.

## `dev/ep-xt9h93jnn2`

* Конфиг `dev-mixed`, seed 203; период 2026-08-01 … 2026-11-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 291 проводок, 40 счетов, 22 платежей, 156 курсов.
* Ошибки: fx_rate/adjacent_day, payment_allocation/partial; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, unidentified_receipt.
* simple_reconcile: TP 1 · FP 0 · FN 1 · reward +0.307 · 14 шагов.

## `dev/ep-nge3f44dyd`

* Конфиг `dev-global`, seed 204; период 2026-11-01 … 2027-01-01; пояс Asia/Tokyo (UTC+9:00).
* Размер: 378 проводок, 44 счетов, 27 платежей, 162 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, multi_invoice_payment, refund, bank_fee, boundary_time, unidentified_receipt, night_fx, overpayment, weekend_fx.
* simple_reconcile: TP 0 · FP 1 · FN 0 · reward -1.000 · 16 шагов.

## `dev/ep-4qcfb8dahb`

* Конфиг `dev-global`, seed 205; период 2026-02-01 … 2026-05-01; пояс Pacific/Pago_Pago (UTC-11:00).
* Размер: 317 проводок, 41 счетов, 22 платежей, 150 курсов.
* Ошибки: fx_rate/adjacent_day, payment_allocation/partial, payment_allocation/partial, period_cutoff/backdated_posting; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, partial_open, refund, bank_fee, boundary_time, credit_note_reissue, night_fx, weekend_fx.
* simple_reconcile: TP 4 · FP 1 · FN 0 · reward +0.752 · 14 шагов.

## `dev/ep-wm5bxcrh9d`

* Конфиг `interaction-heavy`, seed 206; период 2026-07-01 … 2026-10-01; пояс Asia/Dubai (UTC+4:00).
* Размер: 294 проводок, 41 счетов, 21 платежей, 237 курсов.
* Ошибки: fx_rate/adjacent_day, duplicate_invoice/copy_as_posted; сценарии: duplicate_fx.
* Корректные «двойники»: repeat_amount, split_payment, multi_invoice_payment, partial_open, rounding_residual, boundary_time, unidentified_receipt.
* simple_reconcile: TP 2 · FP 1 · FN 0 · reward +0.572 · 15 шагов.

## `dev/ep-vbg7s7cfhm`

* Конфиг `interaction-heavy`, seed 207; период 2026-08-01 … 2026-11-01; пояс America/Lima (UTC-5:00).
* Размер: 294 проводок, 40 счетов, 19 платежей, 156 курсов.
* Ошибки: fx_rate/historical_rate, payment_allocation/partial, payment_allocation/unallocated; сценарии: partial_fx_cutoff.
* Корректные «двойники»: recurring_rent, partial_open, refund, bank_fee, boundary_time, night_fx, weekend_fx.
* simple_reconcile: TP 2 · FP 0 · FN 1 · reward +0.574 · 14 шагов.

## `dev/ep-vk7pc3rd7r`

* Конфиг `interaction-heavy`, seed 208; период 2026-08-01 … 2026-11-01; пояс Asia/Kolkata (UTC+5:30).
* Размер: 319 проводок, 40 счетов, 27 платежей, 156 курсов.
* Ошибки: fx_rate/wrong_pair, duplicate_invoice/copy_as_posted, fx_rate/adjacent_day, payment_allocation/partial; сценарии: duplicate_fx, partial_fx_cutoff.
* Корректные «двойники»: repeat_amount, split_payment, partial_open, bank_fee, rounding_residual, boundary_time, unidentified_receipt, night_fx.
* simple_reconcile: TP 2 · FP 1 · FN 2 · reward +0.115 · 15 шагов.

## `dev/ep-md93e84dvw`

* Конфиг `clean-only`, seed 209; период 2026-07-01 … 2026-10-01; пояс Asia/Almaty (UTC+5:00).
* Размер: 318 проводок, 39 счетов, 30 платежей, 158 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, night_fx, weekend_fx.
* simple_reconcile: TP 0 · FP 1 · FN 0 · reward -1.000 · 15 шагов.

## `dev/ep-3j67p4jary`

* Конфиг `clean-only`, seed 210; период 2026-07-01 … 2026-10-01; пояс Asia/Tokyo (UTC+9:00).
* Размер: 330 проводок, 42 счетов, 31 платежей, 158 курсов.
* Ошибки: нет.
* Корректные «двойники»: recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, overpayment.
* simple_reconcile: TP 0 · FP 2 · FN 0 · reward -1.000 · 15 шагов.
