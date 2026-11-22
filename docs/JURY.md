# Памятка для жюри: как проверить AuditEnv своими политиками и закрытыми эпизодами

Всё ниже работает офлайн, в контейнере (`make docker-build`, затем
`docker run --rm --network none --cpus 2 --memory 4g auditenv <команда>`) или локально после
`make venv`. Код возврата ≠ 0 означает провал. English summary: [`README.en.md`](../README.en.md).

## 1. Ваши 4 политики: три способа подключить

Среда и оценщик всегда живут в **процессе оценщика**; ваша политика эталона не видит.

### 1а. Любая программа через JSON‑строки (`--policy-cmd`) — рекомендуемый способ

Программа читает из stdin строку `{"observation": ..., "reward": ..., "terminated": ..., "truncated": ...}`
и отвечает одной строкой `{"action": {"tool": "...", "args": {...}}}`; в конце приходит `{"close": true}`.
Полный протокол — [`docs/ADAPTER.md`](ADAPTER.md), пример на ~40 строк — `examples/minimal_agent.py`.

```bash
python -m auditenv run --policy-cmd "python examples/minimal_agent.py" --seed 12 --config dev-mixed
```

```bash
python -m auditenv run --policy-cmd "python my_policy.py" --episode-dir episodes/dev/<episode_id> --mode eval --log /tmp/grader_log.jsonl
```

Процесс политики запускается в песочнице: пустой cwd, окружение `PATH/TZ/LANG` без соли и путей,
rlimits, под root — пользователь `nobody` (таблица в `docs/ADAPTER.md`). Если вашей программе нужен
свой интерпретатор или пакеты — укажите абсолютный путь к нему в `--policy-cmd`.

**Если запускаете без Docker от root:** политика стартует от `nobody`, поэтому `nobody` должен иметь право
войти в папку репозитория и запустить `.venv/bin/python`. Не клонируйте в `/root` или другую папку с правами
`700` — иначе `tests/test_batch_c.py::test_child_limits_are_applied_and_python_still_starts` упадёт с
`PermissionError`. Подойдёт, например, `/opt` или `/home/<user>`; в Docker (`make docker-check`) это не нужно —
там проверка идёт от пользователя `auditor`.

### 1б. Сервер и клиент (`serve` / `AuditEnvClient`) — для фреймворков обучения

```bash
python -m auditenv serve --mode train
```

Запросы — по строке JSON: `{"cmd": "reset", "seed": 7, "config": "dev-mixed"}`,
`{"cmd": "step", "action": {...}}`, `{"cmd": "close"}`. Из Python то же самое делает клиент — среда
и эталон в дочернем процессе, у клиента API как у Gymnasium:

```python
from auditenv.serve import AuditEnvClient
with AuditEnvClient(mode="train") as env:
    obs, info = env.reset(seed=7, config="dev-mixed")
    obs, reward, terminated, truncated, info = env.step({"tool": "list_records", "args": {"table": "ledger"}})
```

### 1в. Python API в одном процессе — быстро, но без изоляции

```python
import auditenv
env = auditenv.make("dev-mixed", mode="train")
obs, info = env.reset(seed=7)                      # или env.reset(episode_dir="episodes/dev/<id>")
obs, reward, terminated, truncated, info = env.step({"tool": "submit", "args": {"findings": []}})
```

Политика и эталон здесь в одной памяти — годится для отладки, **не** для честного прогона.

## 2. Закрытые эпизоды с `AUDITENV_SEED_SALT`

Генератор открыт, поэтому без соли эпизод (и эталон) можно восстановить перебором seed. Секретная
соль меняет все под‑seed; открытые тесты её игнорируют.

```bash
export AUDITENV_SEED_SALT='<ваш секрет>'
python -m auditenv run --policy-cmd "python my_policy.py" --seed 123456 --config dev-mixed --mode eval --log /tmp/grader_log.jsonl
```

* `run --seed` генерирует эпизод **в памяти** оценщика: `grader/` на диск не пишется вообще.
* Если эпизоды нужны файлами (например, для повторных прогонов), `generate` пишет `public/` и
  `grader/` раздельно — держите папку недоступной для пользователя политики (`chmod 700`):

```bash
python -m auditenv generate --seed 123456 --config dev-mixed --out /secret/ep1
```

* Конфиги: `train-easy`, `train-global`, `dev-mixed`, `dev-global`, `interaction-heavy`,
  `clean-only`, `stress` (`configs/`). Журнал оценщика с цепочкой хешей проверяется командой
  `python -m auditenv verify-log /tmp/grader_log.jsonl`.
* Не запускайте `make check` с установленной солью: табло сгенерирует солёные эпизоды, отличные от
  закоммиченных открытых (скрипт предупредит).

## 3. 20 парных преобразований

Пара = эпизод и его двойник с переставленными строками и **непрозрачными** новыми ID (без префиксов,
длина 12–64); эталон переносится по таблице переименований. Хорошая среда и честная политика
дают на паре одинаковые награду и F1.

Одной командой, для любой политики, всё в памяти (с солью — закрытые эпизоды):

```bash
python -m auditenv jury-pairs --policy-cmd "python my_policy.py" --n 20 --config dev-mixed --json /tmp/pairs.json
```

Печатает 20 строк `reward / reward_twin`, `F1 / F1_twin` и итог `jury-pairs: 20/20 pairs equal`;
код возврата 1 при любом расхождении. `--policy simple_reconcile` (или `oracle`, `flag_all`,
`random_explorer`) — то же для встроенных политик.

Вручную, файлами (двойник получает `grader/id_map.json` — старый ID → новый):

```bash
python -m auditenv transform --episode-dir episodes/dev/<episode_id> --out /tmp/twin --seed 5 --opaque-ids
python -m auditenv run --policy-cmd "python my_policy.py" --episode-dir episodes/dev/<episode_id>
python -m auditenv run --policy-cmd "python my_policy.py" --episode-dir /tmp/twin
```

## 3а. Проверить оценщик своим ответом, набранным вручную

Инструмент оценщика (читает `grader/` открытого эпизода): для каждого вывода показывает, с каким
issue он сопоставлен или код причины несовпадения, затем TP/FP/FN, P/R/F1 и награду за N шагов. Файл —
`{"episode_id", "findings": [...]}` или просто список выводов. Разбор ошибок эпизода «до/после» —
`python -m auditenv explain episodes/dev/<episode_id>` (HTML).

```bash
python -m auditenv grade episodes/dev/<episode_id> /tmp/my_findings.json --steps 10
```

## 4. Обязательные проверки раздела 10 → наша команда → где смотреть

Одна команда покрывает всё: `make check` (или `make docker-check`); табло — `reports/selfcheck.md`.
Ниже — как проверить пункт отдельно (`pytest -q <тест>`).

| Проверка из раздела 10 | Команда | Где смотреть |
|---|---|---|
| Формы reset / step | `pytest -q tests/test_contract.py -k "reset_shape or step_shape"` | `tests/test_contract.py::test_reset_shape`, `test_step_shape_and_zero_reward`; табло «Контракт» |
| Лимит 50 строк | `pytest -q tests/test_contract.py -k page_limit` | `tests/test_contract.py::test_page_limit_50` |
| Стабильные курсоры; курсор из чужого эпизода | `pytest -q tests/test_contract.py -k cursor` | `test_cursors_stable_and_complete`, `test_cursor_from_other_episode_or_table` |
| Неизвестные tool и ID; шаг расходуется на ошибку | `pytest -q tests/test_contract.py -k "unknown or bad_args"` | `test_unknown_tool_and_ids_consume_steps`, `test_bad_args`; fuzz — `tests/test_fuzz.py` |
| 100 шагов → truncated; тайм‑аут; шаг после конца | `pytest -q tests/test_contract.py -k "100 or timeout or after_end"` | `test_100_steps_truncated`, `test_submit_on_step_100_is_allowed`, `test_timeout_truncates`, `test_step_after_end` |
| Калькулятор против `__import__`, лямбд, `9**9**9`, длинных строк, деления на 0 | `pytest -q tests/test_calculator.py` | `tests/test_calculator.py::test_rejected` |
| Режим eval без награды и info | `pytest -q tests/test_contract.py -k eval_mode` | `test_eval_mode_hides_reward_and_info`; `tests/test_runner.py::test_eval_mode_child_never_sees_reward` |
| Изоляция двух env | `pytest -q tests/test_contract.py -k "isolat"` | `test_two_envs_isolated`, `test_reset_isolates_state` |
| Инварианты чистой книги на 50 seed | `pytest -q tests/test_data.py -k clean_book_invariants` | `tests/test_data.py::test_clean_book_invariants`; табло «Данные» |
| Каждый тип ошибки нарушает ровно свой инвариант на expected_amount | `pytest -q tests/test_data.py -k exactly_its_invariant` | `test_error_breaks_exactly_its_invariant`; `python -m auditenv verify-provenance` |
| Каждое доказательство доступно через инструменты | `pytest -q tests/test_data.py -k reachable` | `test_every_evidence_id_reachable_through_tools` |
| `validate_truth` находит все issue | `pytest -q tests/test_data.py -k validate_truth` | `test_validate_truth_agrees_on_50_seeds`; независимо: `python -m auditenv verify-independent --seeds 500` |
| На чистых эпизодах truth пуст и решатель ничего не находит | `pytest -q tests/test_data.py -k clean_episodes` | `test_clean_episodes_have_empty_truth_and_solver_finds_nothing` |
| Oracle лучше пустого ответа; пустой ответ на чистых лучше обвинения | `pytest -q tests/test_reward.py -k "beats or silence"` | `test_oracle_beats_silence_on_erroneous`, `test_silence_beats_any_accusation_on_clean` |
| Дубли не дают выгоды; flag_all плохой | `pytest -q tests/test_reward.py -k "duplicates or flag_all"` | `test_duplicates_give_no_gain`, `test_flag_all_is_bad`; таблица политик в `reports/selfcheck.md` |
| 10 и 50 шагов отличаются ровно на 0.08 | `pytest -q tests/test_reward.py -k step_cost` | `test_step_cost_10_vs_50_is_exactly_0_08` |
| explanation не влияет | `pytest -q tests/test_reward.py -k explanation` | `test_explanation_has_no_effect`; строка `attack:junk_explanation` в табло |
| Угаданный ID без доказательств = FP; неверная валюта = FP | `pytest -q tests/test_reward.py -k "guessed or currency"` | `test_guessed_id_without_evidence_is_fp`, `test_wrong_currency_is_fp` |
| Неверный JSON = −1 | `pytest -q tests/test_reward.py -k minus_one` | `test_bad_json_is_minus_one`; `tests/test_contract.py::test_invalid_structure_minus_one` |
| Перестановка findings не меняет F1 | `pytest -q tests/test_reward.py -k order` | `test_finding_order_irrelevant` |
| Property: лишний FP не повышает, лишний TP не понижает | `pytest -q tests/test_reward.py -k property` | `test_property_extra_fp_never_helps`, `test_property_extra_tp_never_hurts` |
| Одинаковые seed/config/действия → одинаковые байты, траектории, награды | `pytest -q tests/test_repro.py` | `test_same_seed_same_bytes`, `test_same_actions_same_trajectory_and_rewards`; `python -m auditenv replay` |
| Transforms сохраняют награду oracle и F1 | `python -m auditenv jury-pairs --policy oracle --n 20` | `tests/test_repro.py::test_transform_preserves_oracle_and_f1`; табло «Воспроизводимость» |
| Golden‑хеши 3 эпизодов | `pytest -q tests/test_repro.py -k golden` | `tests/golden_hashes.json` |
| Leakscan: нет issue_id, типов рядом с affected_ids, путей `grader/`, seed | `python -m auditenv leakscan` | `tests/test_leaks.py`; изоляция процесса — `tests/test_isolation.py` |

**Сверх раздела 10:** насколько тесты оценщика вообще ловят баги — `make mutation`
(22 намеренные ошибки в matcher / reward / normalize / schema; отчёт `reports/mutation.md`);
независимый проверяльщик без импорта `auditenv` — `tools/verify_independent.py`; ручная сверка
калькулятором — `docs/MANUAL_AUDIT.md`; эталонные компании, собранные вручную, — `tests/fixtures/`.
