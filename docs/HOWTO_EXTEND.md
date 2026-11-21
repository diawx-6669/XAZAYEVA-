# Как быстро расширить среду (шпаргалка для финала)

Общее правило после **любого** изменения генератора: поднять `version` в затронутых конфигах →
`python -m auditenv lock-configs` → строка в `configs/CHANGELOG.md` → `make episodes golden
trajectories` → `python -m auditenv docs-check --fix` → `make check` (должно быть `ALL GREEN`).
Тест `tests/test_configs_lock.py` не даст забыть про версию.

## 1. Новый тип ошибки (отрепетировано: `vat_error`, 242 секунды)

Репетиция — в ветке `final-rehearsal` (в `main` **не сливается**), полный патч кода:
[`docs/rehearsal/vat_error.patch`](rehearsal/vat_error.patch) (27 файлов). **Раунд 3:** патч перенесён на
текущий код (после слияния с `main`: построчная выручка, свой валидатор схем) — при переносе вручную
доделаны 2 места (`grader/validate_truth.py::verify_evidence`, `tools/verify_independent.py::evidence_amount`)
и версии конфигов 2.1 → 2.2. Теперь он применяется без правок: `git apply docs/rehearsal/vat_error.patch`
(проверяется тестом `tests/test_round3.py::test_vat_rehearsal_patch_applies_cleanly`). После него — общее правило выше
(`lock-configs`, `export`, `golden`, `trajectories`, `python tools/build_replay.py`, `export-audit`,
`docs-check --fix`, ≈ 15 с); в ветке `final-rehearsal` весь pytest зелёный и `make check` — `ALL GREEN`.
Время от создания ветки до зелёного pytest — **242 с** (Claude Code; человеку по этому списку —
порядка 1–2 часов), затем `make check` — 1 мин 43 с, табло 90/90, `ALL GREEN`.

| Шаг | Файл | Что сделать |
|---|---|---|
| 1 | `auditenv/generator/errors/<type>.py` | класс `ErrorType` с `@register`: `applicable`, `inject` (снимок «до», мутация, перепроводка), `canonical_ids`, `evidence_sets` (1–3 набора ≤ 6 ID, объединение ≤ 10), `expected_amount` |
| 2 | `auditenv/generator/errors/__init__.py`, `errors/base.py::ORDER` | импорт модуля; место в фиксированном порядке мутаций |
| 3 | `auditenv/generator/invariants.py` | новый инвариант `check_<x>` в `INVARIANTS` и `check_all` (в чистой книге — пусто) |
| 4 | `auditenv/grader/validate_truth.py` | `TYPE_OF_INVARIANT[<inv>] = <type>`; ветка в `verify_evidence` (сумма только из набора) |
| 5 | `tools/verify_independent.py` | своя (независимая!) реализация правила в `solve` и в `evidence_amount` |
| 6 | `schemas/findings.schema.json`, `schemas/truth.schema.json`, `schemas/config.schema.json` | тип в `enum`; вес в `errors`; новые ключи данных |
| 7 | `auditenv/config.py::DEFAULT_CONFIG` | новые ключи со значением «выключено», чтобы старые эпизоды не менялись |
| 8 | `auditenv/generator/story.py` | данные, на которых тип вообще возможен (у `vat_error` — строка «VAT 12%») |
| 9 | `auditenv/env/env.py::task_text` | одна фраза про тип и `affected_ids` |
| 10 | списки `TYPES` в `policies/flag_all.py`, `policies/attacks.py`, `leakscan.py`, `analysis.py`, `exploit_search.py` | добавить тип |
| 11 | `tests/test_data.py::single` | дать данные для типа (`vat_share`); тесты, параметризованные по `TYPE_OF_INVARIANT`, подхватят тип сами |

**Урок репетиции:** первый вариант портил и оплаченные счета — новый итог превращал платёж в
переплату, и ломались **два** инварианта. Это поймали `validate` и тест «каждая ошибка ломает
ровно свой инвариант». Правило: цели мутации ограничивать так, чтобы её последствия не
растекались по другим документам.

## 2. Новый отвлекающий (корректный) случай

| Файл | Что сделать |
|---|---|
| `auditenv/generator/story.py` | имя в `DISTRACTOR_KINDS`; блок в `StoryBuilder.build` (или в `plan_payments` для платежей); если это «двойник» ошибки — в `LOOKALIKES[тип]`; если документу не нужна авто‑оплата — тег в `NO_PAY_TAGS` |
| `schemas/config.schema.json`, `auditenv/config.py::DEFAULT_CONFIG` | доля `distractors.<имя>` |
| `auditenv/generator/errors/*.py` | если ошибки на таких документах разрешимы — тег в `ALLOW` нужных типов (иначе `special()` защищает) |
| тесты | `tests/test_data.py::test_distractors_are_generated_and_clean` (список видов), `tests/test_surface.py` (не стал ли признак ярлыком), шаг `lint` |

Сканер совпадений сам отбросит эпизод, если новый случай случайно выглядит как ошибка для
независимого решателя.

## 3. Сменить правило даты курса (например, «курс даты по UTC» или «курс предыдущего дня»)

| Файл | Что сделать |
|---|---|
| `auditenv/timeutil.py::policy_rate_date` | правило выбора даты |
| `auditenv/generator/books.py::Book.rate_date`, `story.py::rate_for` | откуда берётся дата транзакции |
| `auditenv/env/data.py::PublicData.correct_rate` / `calendar_rate_date` | то же для решателя по открытым данным |
| `auditenv/generator/export.py::make_policy` | `fx_rate_date`, `fx_rate_date_basis`, `fx_missing_rate` — текст правила для агента |
| `tools/verify_independent.py::Episode.rate_day / rate` | независимая реализация |
| `auditenv/generator/errors/fx_rate.py::wrong_rates` | смысл варианта `utc_date` (при правиле UTC он станет «local_date») |
| `auditenv/policies/simple_reconcile.py` | демо‑политика |
| `docs/CONTRACT.md`, `docs/DESIGN.md`, `docs/MANUAL_AUDIT.md` | описание правила |
| тесты | `tests/test_batch_b.py::test_fx_variants`, `test_data.py`, шаги `verify-independent` и `verify-provenance` |

## 4. Изменить допуск по сумме

Только конфиг: `"tolerance_minor": N` (0…49). Значение уходит в `truth.json`, оценщик берёт его
оттуда, а текст задачи сообщает агенту. Проверка: `tests/test_batch_a.py::test_tolerance_from_config_travels_to_grader_and_task`.
Не забыть версию конфига и `lock-configs`.

## 5. Эпизоды на ~2000 проводок и 12 ошибок

Конфиг (например, `configs/big.json`, `"version": "1.0"`):

```json
{"name": "big", "version": "1.0", "n_invoices": [230, 260], "n_entities": [40, 60], "period_months": 6,
 "period_starts": ["2026-01"], "n_errors": [12, 12], "clean_probability": 0.0,
 "foreign_currencies": ["USD", "EUR", "JPY", "KWD"], "n_foreign": [3, 4],
 "interactions": {"partial_fx_cutoff": 1.0, "duplicate_fx": 1.0}}
```

Замер (после слияния с `main`: 3–7 позиций на счёт, выручка построчно): 1 858–2 046 проводок,
ровно 12 ошибок, генерация 0.4–0.6 с, эталон валиден, oracle = 1.0, simple_reconcile — 58–65 шагов
из 100. Затем `python -m auditenv lock-configs`.

## 6. Подключить чужую политику

Ничего в коде менять не нужно:

```bash
python -m auditenv run --policy-cmd "python their_agent.py" --episode-dir episodes/dev/<id> --mode eval --log log.jsonl
```

Протокол и песочница — [`docs/ADAPTER.md`](ADAPTER.md); пример на ~35 строк —
`examples/minimal_agent.py`; для фреймворков с объектом `env` — `auditenv.serve.AuditEnvClient`.
Чтобы политика попала в траектории: добавить имя в `cli.py::AGENT_BASELINES` (если она в пакете) и
`make trajectories`.
