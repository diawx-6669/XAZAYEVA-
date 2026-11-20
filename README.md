# AuditEnv — RL‑среда для ИИ‑аудитора (Genesis Hackathon, FinTech)

Воспроизводимый симулятор для дообучения модели финансового аудита. По `seed` и `config`
генерируется **вымышленная** компания за один отчётный период: скрытая история событий →
документы и проводки → внесённые ошибки с записанной причиной → закрытый эталон. Агент через
пять узких инструментов (не больше 100 шагов) читает записи и отправляет выводы с
доказательствами. Оценщик вне процесса агента сопоставляет выводы с эталоном и считает награду.

Это **среда и оценщик**, а не платёжное приложение, чат‑бот или модель. Веса мы не обучаем и
об улучшении моделей не заявляем (см. [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

## Запуск одной командой

```bash
make docker-check
```

Собирает образ `python:3.11-slim` и запускает полную проверку **без сети** с лимитами жюри:
`docker run --rm --network none --cpus 2 --memory 4g auditenv`. Без Docker:

```bash
make venv
```

```bash
make check
```

`make check` = весь pytest (<!--fact:n_tests-->376<!--/fact--> тестов, включая hypothesis и 4×50 seed для решателя) + табло self‑check на 20
эпизодах и 20 парных преобразованиях + leakscan + replay траекторий. Результат печатается и
пишется в `reports/selfcheck.md` / `reports/selfcheck.json`, журнал оценщика —
`reports/grader_log.jsonl`. Код возврата ≠ 0, если хоть одна проверка упала.

Измерено (контейнер, `--cpus 2 --memory 4g --network none`): `make check` — 36 с целиком,
пик памяти ≈ 70 МиБ. Эпизод `stress` (1 354–1 522 проводки, ~640 документов): генерация
0,3–0,5 с, прогон simple_reconcile 56 шагов ≈ 0,1 с — с запасом под лимит 60 с.

**Закрытый прогон (жюри).** Генератор открыт, поэтому для скрытых seed задайте секретную соль —
без неё агент мог бы перебором seed восстановить эпизод и эталон:

```bash
docker run --rm --network none --cpus 2 --memory 4g -e AUDITENV_SEED_SALT=<секрет> auditenv \
  python -m auditenv run --policy simple_reconcile --seed 123456 --config dev-mixed --mode eval --log /tmp/grader_log.jsonl
```

Соль меняет все эпизоды, но не передаётся в процесс агента (`runner.py` собирает его окружение
явно). Открытые train/dev‑эпизоды сгенерированы без соли и воспроизводятся по seed из
`episodes/*/index.json`.

Другие команды:

| Команда | Что делает |
|---|---|
| `make quick` | быстрые тесты + 3 эпизода × 4 политики (≈17 с) |
| `make episodes` | перегенерирует 10 train + 10 dev эпизодов в `episodes/` из `configs/splits.json` |
| `make trajectories` | пишет `trajectories/trajectories.jsonl` (все политики, кроме oracle) и прогоняет leakscan |
| `make demo` | `scripts/demo.sh`: check → эпизод с взаимодействующими ошибками шаг за шагом → атака flag_all → двойник после transforms |
| `python -m auditenv generate --seed 7 --config dev-mixed --out /tmp/ep` | один эпизод на диск (`public/` и `grader/` раздельно) |
| `python -m auditenv run --policy simple_reconcile --episode-dir episodes/dev/<id> --mode eval --log log.jsonl` | прогон политики в отдельном процессе |
| `python -m auditenv replay` | повтор действий из траекторий и побайтовое сравнение наблюдений и наград |

## Как устроен эпизод

```
seed, config ──► story (скрытые события, курсы) ──► books (документы + двойная запись)
                    │                                   │
                    │                    сканер совпадений: независимый решатель
                    │                    должен НИЧЕГО не найти в чистой книге,
                    │                    иначе перегенерация со следующим под‑seed
                    ▼                                   ▼
             errors/* + interactions  ──►  мутации в фиксированном порядке, before/after
                                                        ▼
     public/  manifest.json ledger.csv invoices.jsonl payments.jsonl fx.csv policy.json
     grader/  truth.json provenance.json          (агент их не видит)
```

* Деньги — только `int` в минимальных единицах; курсы — десятичные строки, `Decimal`,
  `ROUND_HALF_EVEN`. Все суммы в `ledger.csv` — в базовой валюте.
* Время — ISO‑8601 со смещением; документы пишутся то в локальном смещении, то в UTC
  (доля задаётся конфигом), поэтому «UTC‑ловушка» на границе периода реальна.
* Валюты KZT/USD/EUR (экспонента 2), JPY (0), KWD (3). Часовые пояса без перехода на летнее
  время: Asia/Almaty, Tashkent, Dubai, Kolkata (+05:30), Tokyo, America/Bogota, Lima (−05:00).
* Отсутствующая ссылка — пустая ячейка CSV / `null` в JSON, не угаданная связь.

Четыре типа ошибок (каждый — один модуль в `auditenv/generator/errors/`, включаются
независимо в конфиге): `duplicate_invoice`, `payment_allocation` (не распределён / частично),
`fx_rate` (соседний рабочий день / дата UTC вместо локальной / перевёрнутый курс),
`period_cutoff` (счёт вне периода по местному времени, записанный в UTC). Два сценария
взаимодействия: `partial_fx_cutoff`, `duplicate_fx`. <!--fact:n_distractors-->14<!--/fact--> корректных отвлекающих
случаев (аренда с одинаковой суммой, оплата частями, платёж на 2–3 счёта, законная частичная
оплата, возврат, банковская комиссия, остаток округления 1 ед., операции в 23:50 и 00:05,
credit note с перевыставлением, неопознанный платёж на 2400, повтор суммы у другого клиента).

## Контракт среды

```python
from auditenv.env.env import AuditEnv
env = AuditEnv(mode="train")                     # "eval": reward=0, info={}, итог только в журнал оценщика
obs, info = env.reset(seed=7, config="dev-mixed") # или env.reset(episode_dir="episodes/dev/<id>")
obs, reward, terminated, truncated, info = env.step(
    {"tool": "list_records", "args": {"table": "ledger", "limit": 50}})
```

Инструменты: `list_records(table, cursor, limit≤50)`, `get_record(table, id)`,
`get_document(doc_id)`, `calculator(expression)`, `submit(findings)`. Ошибки — только код:
`unknown_tool | bad_args | not_found | invalid_cursor | calc_error | episode_over`, каждая
тратит шаг. Терминальная награда: `clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)`;
экспериментальная (TP только при реально увиденных доказательствах) показывается отдельно.
Схемы всех файлов, действий, наблюдений, findings и truth — в [`schemas/`](schemas/).

## Структура

```
auditenv/
  money.py ids.py timeutil.py config.py canon.py schemas.py paths.py
  generator/  story.py books.py invariants.py errors/{base,duplicate_invoice,payment_allocation,fx_rate,period_cutoff}.py
              interactions.py transforms.py episode.py export.py
  env/        env.py tools.py calculator.py cursors.py errors.py data.py
  grader/     schema.py normalize.py matcher.py reward.py validate_truth.py log.py core.py
  policies/   random_explorer.py simple_reconcile.py flag_all.py oracle.py attacks.py base.py
  runner.py   selfcheck.py leakscan.py cli.py
configs/      train-easy, dev-mixed, clean-only, interaction-heavy, stress (+ splits.json с seed'ами)
schemas/      manifest, ledger_row, invoice, payment, fx, policy, action, observation, findings, truth, config
episodes/     train/ (10) и dev/ (10): <episode_id>/public/*, <episode_id>/grader/*, index.json
trajectories/ trajectories.jsonl (<!--fact:traj_lines-->1193<!--/fact--> строк, <!--fact:traj_runs-->64<!--/fact--> прогонов: <!--fact:traj_policies-->flag_all, hung, random_explorer, simple_reconcile, step_burner<!--/fact-->)
reports/      selfcheck.md, selfcheck.json (генерируются make check)
tests/        pytest + hypothesis
docs/         CASE.md, DESIGN.md, LIMITATIONS.md, FAILURES.md
```

## Карта соответствия «пункт ТЗ → файл/функция → тест»

| Пункт кейса | Где реализовано | Чем проверено |
|---|---|---|
| 02 Четыре независимо настраиваемых типа ошибок | `generator/errors/*.py`, реестр `errors/base.py::REGISTRY`, веса `config.errors` | `test_data.py::test_error_breaks_exactly_its_invariant` |
| 02 Два сценария взаимодействия | `generator/interactions.py` | `test_data.py::test_interaction_scenarios_present`, `test_partial_fx_cutoff_gives_two_issues_on_one_payment` |
| 02 Чистые компании и отвлекающие случаи | `generator/story.py` (`DISTRACTOR_KINDS`), `configs/clean-only.json` | `test_data.py::test_clean_episodes_have_empty_truth_and_solver_finds_nothing`, `test_distractors_are_generated_and_clean` |
| 02 Скрытая история → документы → ошибки с причиной | `story.py` → `books.py` → `episode.py::inject_errors`, before/after в `provenance.json` | `test_data.py::test_clean_book_invariants` (50 seed) |
| 02 Эталон = реальное расхождение, доступные доказательства | `generator/invariants.py`, `grader/validate_truth.py::verify_evidence` | `test_data.py::test_every_evidence_id_reachable_through_tools`, `test_validate_truth_agrees_on_50_seeds` (4×50) |
| 02 Вариация имён, ID, порядка, сумм, валют, поясов | `ids.py`, `story.py`, `export.py` (поток `order`) | `test_data.py::test_varied_names_ids_currencies_timezones` |
| 03 manifest.json и форматы значений | `generator/export.py`, `schemas/*.schema.json` | `selfcheck` блок «Данные» (`validate_public`), `test_data.py::test_clean_book_invariants` |
| 03 Явные null | `export.py` (пустая ячейка ↔ `None`) | `test_data.py::test_null_references_are_explicit` |
| 03 Закрытые truth/provenance, не утекают | `export.py::write_episode`, `leakscan.py` | `test_leaks.py`, `selfcheck` «leakscan clean» |
| 04 reset/step, Gymnasium‑контракт | `env/env.py::AuditEnv` | `test_contract.py::test_reset_shape`, `test_step_shape_and_zero_reward` |
| 04 Воспроизводимость, изоляция reset | `ids.py::derive_seed`, `env.reset` | `test_repro.py`, `test_contract.py::test_reset_isolates_state`, `test_two_envs_isolated` |
| 04 Пять действий, страница ≤ 50, стабильные курсоры | `env/tools.py`, `env/cursors.py` (HMAC) | `test_contract.py::test_page_limit_50`, `test_cursors_stable_and_complete`, `test_cursor_from_other_episode_or_table` |
| 04 Калькулятор: только арифметика | `env/calculator.py` (AST + Decimal) | `test_calculator.py` |
| 04 Ограниченные ошибки, шаг расходуется | `env/errors.py`, `env/env.py::step` | `test_contract.py::test_unknown_tool_and_ids_consume_steps`, `test_bad_args`, `test_fuzz.py` |
| 04 100 шагов, submit, truncated, тайм‑аут | `env/env.py` | `test_contract.py::test_100_steps_truncated`, `test_submit_on_step_100_is_allowed`, `test_timeout_truncates`, `test_step_after_end` |
| 04 Награда только в train, eval без диагностики | `env/env.py::_finish` | `test_contract.py::test_eval_mode_hides_reward_and_info`, `test_runner.py::test_eval_mode_child_never_sees_reward` |
| 05 Схема findings, лимиты, неверная структура = −1 | `schemas/findings.schema.json`, `grader/schema.py` | `test_reward.py::test_bad_json_is_minus_one`, `test_float_amount_rejected`, `test_contract.py::test_invalid_structure_minus_one` |
| 05 Взаимно однозначное сопоставление, допуск, ничьи | `grader/matcher.py`, `grader/normalize.py` | `test_reward.py::test_tie_break_smallest_issue_then_index`, `test_tolerance_boundary`, `test_currency_and_ids_are_normalized` |
| 05 P/R/F1 и краевые случаи | `grader/reward.py::prf` | `test_reward.py::test_metrics_edge_cases` |
| 05 Общая + экспериментальная награда отдельно | `grader/reward.py`, `grader/core.py` | `test_reward.py::test_experimental_reward_requires_seen_evidence` |
| 05 Тесты: ответ > молчание, молчание > обвинение, дубли, flag_all, стоимость шагов | `tests/test_reward.py` | `test_oracle_beats_silence_on_erroneous`, `test_silence_beats_any_accusation_on_clean`, `test_duplicates_give_no_gain`, `test_flag_all_is_bad`, `test_step_cost_10_vs_50_is_exactly_0_08` |
| 05 Угаданные ID, неподтверждённые доказательства, валюты, повтор, тайм‑аут | `policies/attacks.py` | `test_reward.py::test_attacks_*`, `test_guessed_id_without_evidence_is_fp`, `test_wrong_currency_is_fp`, `selfcheck` «re-submission is ignored» |
| 05 Property‑based: лишний FP не помогает, лишний TP не вредит | — | `test_reward.py::test_property_*` (hypothesis) |
| 06 Безвредные преобразования (порядок, ID) | `generator/transforms.py` | `test_repro.py::test_transform_preserves_oracle_and_f1`, `selfcheck` блок «Воспроизводимость» |
| 06 Четыре политики организаторов | `policies/`, `runner.py` | `test_runner.py`, диагностика в `reports/selfcheck.md` |
| 07 Записанные траектории без эталона | `cli.py::cmd_trajectories`, `trajectories/trajectories.jsonl` | `test_leaks.py::test_committed_trajectories_are_clean`, `python -m auditenv replay` |
| 07 Без сети, платных API, GPU; контейнер; единая команда | `Dockerfile`, `scripts/check.sh`, `Makefile` | `make docker-check` |
| 09 10 train + 10 dev эпизодов | `configs/splits.json`, `episodes/` | `test_repro.py::test_exported_episodes_match_generator` |
| 09 Golden‑хеши | `tests/golden_hashes.json` (`make golden`) | `test_repro.py::test_golden_hashes` |

## Как читать табло (`reports/selfcheck.md`)

* **Контракт и изоляция** — 20 фиксированных проверок reset/step, схем, лимитов, завершения,
  неверного ввода, утечек; баллы = 25 × пройдено / 20.
* **Данные и эталон** — 20 эпизодов (5 clean‑only, 5 interaction‑heavy, 10 dev‑mixed):
  инварианты чистой книги до мутаций; расхождения после мутаций совпадают с объявленными
  ровно по сумме; независимый решатель по открытым данным находит то же, что truth; каждый
  набор доказательств сам по себе позволяет пересчитать сумму.
* **Надёжность награды** — 20 проверок сопоставления, чистых случаев, FP, дублей, стоимости
  шагов и атак.
* **Воспроизводимость** — 20 пар: повторная генерация побайтово равна; replay действий даёт те
  же наблюдения и награды; двойник после перестановки строк и переименования всех ID даёт ту
  же награду и F1 у oracle и simple_reconcile.
* «Инженерия и объяснение» (10 баллов) табло не считает — это оценка жюри.
* Таблица диагностики: средние P, R, F1, возврат, возврат по экспериментальной награде,
  шаги, время на 20 эпизодах в режиме `eval`; колонка «агент видел награду» должна быть «нет».
  У oracle экспериментальная награда низкая намеренно: он не открывал доказательства.

## Важно

Все компании, люди, счета и деньги вымышлены; реальных финансовых данных, платежей и
персональных данных нет. Награда не доказывает пригодность для реального аудита. Лицензия MIT.
