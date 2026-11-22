# Справочник JSON Schema

Сгенерировано `python tools/schemas_doc.py` из `schemas/*.json`; тест `tests/test_round4_schemas_doc.py` сверяет файл
со схемами и проверяет, что каждая схема используется кодом или тестами (нет «мёртвых»). Валидатор —
`auditenv/jsonschema_lite.py`; `python -m auditenv check-schemas` проверяет по ним каждый артефакт репозитория.

## `action.schema.json`



Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `tool` | одно из `list_records`, `get_record`, `get_document`, `calculator`, `submit` | да |
| `args` | object | нет |

Варианты (`oneOf`): 5.
* `tool` = `list_records`: `table`*: одно из `ledger`, `invoices`, `payments`, `fx`, `cursor`: string/null, `limit`: integer (≥ 1, ≤ 50)
* `tool` = `get_record`: `table`*: одно из `ledger`, `invoices`, `payments`, `fx`, `policy`, `id`*: string
* `tool` = `get_document`: `doc_id`*: string
* `tool` = `calculator`: `expression`*: string (длина ≤ 200)
* `tool` = `submit`: `findings`*: → `findings.schema.json`

`*` — обязательное поле.

## `config.schema.json`

Episode generation config

Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `name` | string | да |
| `version` | string | да |
| `base_currencies` | array of (одно из `KZT`, `USD`, `EUR`, `JPY`, `KWD`) (элементов ≥ 1) | да |
| `foreign_currencies` | array of (одно из `KZT`, `USD`, `EUR`, `JPY`, `KWD`) | да |
| `n_foreign` | array of (integer (≥ 0)) (элементов ≥ 2, элементов ≤ 2) | да |
| `foreign_share` | number (≥ 0, ≤ 1) | да |
| `timezones` | array of (одно из `Asia/Almaty`, `Asia/Tashkent`, `Asia/Dubai`, `Asia/Kolkata`, `Asia/Tokyo`, `America/Bogota`, `America/Lima`, `Asia/Kathmandu`, `Pacific/Kiritimati`, `Pacific/Pago_Pago`) (элементов ≥ 1) | да |
| `period_starts` | array of (string (шаблон `^20[0-9]{2}-(0[1-9]\|1[0-2])$`)) (элементов ≥ 1) | да |
| `period_months` | integer (≥ 1, ≤ 6) или array of (integer (≥ 1, ≤ 6)) (элементов ≥ 2, элементов ≤ 2) | да |
| `n_entities` | array of (integer (≥ 1, ≤ 500)) (элементов ≥ 2, элементов ≤ 2) | да |
| `n_invoices` | array of (integer (≥ 5, ≤ 2000)) (элементов ≥ 2, элементов ≤ 2) | да |
| `line_items` | array of (integer (≥ 1, ≤ 10)) (элементов ≥ 2, элементов ≤ 2) | да |
| `utc_share` | array of (integer (≥ 0)) (элементов ≥ 2, элементов ≤ 2) | да |
| `distractors` | object {recurring_rent, repeat_amount, split_payment, multi_invoice_payment, partial_open, refund, bank_fee, rounding_residual, boundary_time, credit_note_reissue, unidentified_receipt, night_fx, overpayment, weekend_fx} | да |
| `clean_probability` | number (≥ 0, ≤ 1) | да |
| `n_errors` | array of (integer (≥ 0, ≤ 12)) (элементов ≥ 2, элементов ≤ 2) | да |
| `errors` | object {duplicate_invoice, payment_allocation, fx_rate, period_cutoff, vat_error} | да |
| `interactions` | object {partial_fx_cutoff, duplicate_fx} | да |
| `min_interactions` | integer (≥ 0, ≤ 2) | да |
| `fx_variants` | object {adjacent_day, utc_date, inverted, historical_rate, wrong_pair, due_date} | да |
| `allocation_variants` | object {unallocated, partial, wrong_invoice} | да |
| `duplicate_variants` | object {copy, paid_twice} | да |
| `cutoff_variants` | object {utc_trap, backdated_posting, prior_period} | да |
| `vat_share` | number (≥ 0, ≤ 1) | нет |
| `min_lookalikes_per_type` | integer (≥ 0, ≤ 3) | да |
| `max_steps` | = `100` | да |
| `tolerance_minor` | integer (≥ 0, ≤ 49) | да |
| `max_attempts` | integer (≥ 1, ≤ 200) | да |

## `findings.schema.json`

findings.json submitted by the agent

Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `episode_id` | string (длина ≥ 1, длина ≤ 64) | да |
| `findings` | array of (object {type, affected_ids, claimed_amount_minor, currency, evidence_ids, explanation}) (элементов ≤ 30) | да |

## `fx.schema.json`

One row of fx.csv. rate = units of target per 1 unit of source, decimal string. Tools add fx_id = fx:DATE:SRC:TGT.

Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `date` | string (шаблон `^\d{4}-\d{2}-\d{2}$`) | да |
| `source_currency` | string (шаблон `^[A-Z]{3}$`) | да |
| `target_currency` | string (шаблон `^[A-Z]{3}$`) | да |
| `rate` | string (шаблон `^[0-9]+(\.[0-9]+)?$`) | да |
| `fx_id` | string (шаблон `^fx:\d{4}-\d{2}-\d{2}:[A-Z]{3}:[A-Z]{3}$`) | нет |

## `grader_log.schema.json`

One line of grader_log.jsonl: a graded episode or an abandoned one. prev_hash chains the lines.


## `index.schema.json`

episodes/<split>/index.json

Тип: array of (object {episode_id, config, seed, public_digest, grader_digest}) (элементов ≥ 10, элементов ≤ 10).

## `info.schema.json`

info returned by reset/step. eval mode: always {}. train mode: {'mode': 'train'} after reset, {} while exploring, metrics at the end.


## `invoice.schema.json`

One line of invoices.jsonl, exactly the case's fields. A credit note has negative amounts and names the cancelled invoice in cancels_invoice_id inside each of its line items.

Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `doc_id` | string | да |
| `invoice_id` | string | да |
| `entity_id` | string | да |
| `issued_at` | string (шаблон `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$`) | да |
| `due_at` | string (шаблон `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$`) | да |
| `currency` | string (шаблон `^[A-Z]{3}$`) | да |
| `total_minor` | integer | да |
| `line_items` | array of (object {description, service_period, quantity, unit_price_minor, amount_minor, cancels_invoice_id}) (элементов ≥ 1) | да |

## `ledger_row.schema.json`

One row of ledger.csv after parsing (empty cell = null). Amounts are base-currency minor units.

Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `row_id` | string | да |
| `timestamp` | string (шаблон `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$`) | да |
| `account` | одно из `1000`, `1200`, `2400`, `4000`, `4100`, `6500`, `7900` | да |
| `debit_minor` | integer (≥ 0) | да |
| `credit_minor` | integer (≥ 0) | да |
| `currency` | string (шаблон `^[A-Z]{3}$`) | да |
| `entity_id` | string/null | да |
| `invoice_id` | string/null | да |
| `payment_id` | string/null | да |

## `manifest.schema.json`



Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `schema_version` | = `1.2` | да |
| `episode_id` | string (шаблон `^ep-[a-z0-9]{10}$`) | да |
| `base_currency` | string (шаблон `^[A-Z]{3}$`) | да |
| `currencies` | object | да |
| `period_start` | string (шаблон `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$`) | да |
| `period_end` | string (шаблон `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$`) | да |
| `timezone` | string | да |
| `counts` | object {ledger, invoices, payments, fx} | да |
| `rounding` | object {mode, fx_conversion} | да |
| `config_version` | string | да |
| `config_hash` | string (шаблон `^[0-9a-f]{16}$`) | да |
| `generator_version` | string | да |

## `observation.schema.json`




## `payment.schema.json`



Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `doc_id` | string | да |
| `payment_id` | string | да |
| `timestamp` | string (шаблон `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$`) | да |
| `currency` | string (шаблон `^[A-Z]{3}$`) | да |
| `amount_minor` | integer (≥ 1) | да |
| `invoice_refs` | array/null (элементов ≥ 1) | да |

## `policy.schema.json`



Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `policy_id` | = `policy` | да |
| `fx_rate_date` | = `transaction_date` | да |
| `fx_rate_date_basis` | string | да |
| `fx_missing_rate` | = `previous_business_day` | да |
| `fx_business_days` | string | да |
| `fx_holidays` | array of (string (шаблон `^[0-9]{4}-[0-9]{2}-[0-9]{2}$`)) | да |
| `fx_rate_meaning` | string | да |
| `fx_conversion` | string | да |
| `period_boundary` | object {start, end, timezone, utc_offset, inclusive_start, inclusive_end} | да |
| `rounding` | = `ROUND_HALF_EVEN` | да |
| `recognition` | = `invoice_issue_date` | да |
| `payment_allocation` | = `invoice_refs_in_order_up_to_open_balance` | да |
| `ar_relief_rate` | string | да |
| `fx_difference_account` | = `7900` | да |
| `unapplied_cash` | string | да |
| `credit_notes` | string | да |
| `revenue_posting` | string | да |
| `vat` | string | да |
| `accounts` | object | да |

## `trajectory.schema.json`

One line of trajectories/trajectories.jsonl (one env transition of one policy run).

Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `episode_id` | string (шаблон `^ep-[a-z0-9]{10}$`) | да |
| `run_id` | string (шаблон `^run-[0-9a-f]{16}$`) | да |
| `policy` | string | да |
| `split` | одно из `train`, `dev` | нет |
| `step` | integer (≥ 0, ≤ 100) | да |
| `action` | any | да |
| `observation` | → `observation.schema.json` | да |
| `reward` | number (≥ -1, ≤ 1) | да |
| `terminated` | boolean | да |
| `truncated` | boolean | да |
| `truncation_reason` | одно из `None`, `max_steps`, `time_limit`, `policy_unresponsive` | нет |
| `run` | object {env_version, generator_version, config_hash, mode, max_steps, time_limit_s} | нет |

## `truth.schema.json`

grader/truth.json - never visible to the agent.

Лишние поля: запрещены.

| Поле | Тип и ограничения | Обязательное |
|---|---|---|
| `episode_id` | string | да |
| `tolerance_minor` | integer (≥ 0, ≤ 49) | да |
| `issues` | array of (object {issue_id, type, affected_ids, expected_amount_minor, currency, evidence_sets}) (элементов ≤ 12) | да |
