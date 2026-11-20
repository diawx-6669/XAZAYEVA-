# Как подключить свою политику (адаптер)

Агент — любая программа, которая читает JSON‑строки из stdin и пишет JSON‑строки в stdout.
Среда и оценщик остаются в родительском процессе; агент не видит ни путей, ни seed, ни эталона.

```bash
python -m auditenv run --policy-cmd "python examples/minimal_agent.py" --seed 7 --config dev-mixed
```

```bash
python -m auditenv run --policy-cmd "python my_agent.py" --episode-dir episodes/dev/<id> --mode eval --log log.jsonl
```

## Протокол

| Направление | Строка | Когда |
|---|---|---|
| среда → агент | `{"observation": {...}, "reward": 0.0, "terminated": false, "truncated": false}` | после `reset` и после каждого шага |
| агент → среда | `{"action": {"tool": "...", "args": {...}}}` | ровно одна строка на каждое наблюдение |
| среда → агент | `{"close": true}` | эпизод закончен — завершитесь |

* Первое наблюдение: `{task, manifest, policy_summary, steps_remaining: 100}`; дальше —
  `{result | error, steps_remaining}`. Инструменты и формы `submit` — в `docs/CONTRACT.md`.
* В режиме `eval` `reward` всегда 0 — итог только в журнале оценщика.
* Нет ответа за отведённое время (60 с на эпизод) или процесс умер — эпизод обрывается
  (`truncated`, `truncation_reason = policy_unresponsive`), оценивается пустой ответ.
* Строка длиннее ~2 МБ — нарушение протокола, эпизод обрывается так же.
* Строка, которая не JSON, — действие `{"tool": "__invalid__"}` → ошибка `unknown_tool`, шаг потрачен.

## Песочница процесса агента (`auditenv/runner.py::ChildPolicy`)

| Ограничение | Значение |
|---|---|
| процесс | отдельная сессия (`start_new_session`), при закрытии убивается вся группа |
| пользователь | если оценщик запущен от root — `nobody` (65534): репозиторий, `truth.json`, журнал оценщика недоступны для записи |
| `RLIMIT_AS` | 1.5 ГиБ |
| `RLIMIT_CPU` | 65 с |
| `RLIMIT_NOFILE` | 64 |
| `RLIMIT_CORE` | 0 |
| `RLIMIT_FSIZE` | 0 (запись в файлы невозможна, `SIGXFSZ` игнорируется → `EFBIG`) |
| `RLIMIT_NPROC` | 64 (вместе с `nobody`) |
| код политики | импортируется из копии пакета только для чтения (`chmod -R a-w`) |
| cwd, `HOME`, `TMPDIR` | пустой временный каталог, удаляется после прогона |
| окружение | собирается явно: без `AUDITENV_SEED_SALT`, без путей к эпизоду |
| после прогона | все процессы `nobody` убиваются, его файлы в `/tmp`, `/var/tmp`, `/dev/shm` удаляются |

Проверено тестами: `tests/test_batch_c.py::test_child_limits_are_applied_and_python_still_starts`
(значения из `/proc/<pid>/limits`), `test_writer_attack_changes_nothing` (агент‑«писатель»
пытается дописать журнал оценщика, переписать `truth.json`, изменить код, оставить файлы в `/tmp`,
запустить демона — sha256 всех файлов до и после совпадают), `test_overlong_line_ends_the_run`.

Без root изоляция слабее (нет смены пользователя) — см. `docs/LIMITATIONS.md`.

## Gymnasium‑клиент для фреймворков обучения

Если вашему коду удобнее объект с `reset/step`, используйте клиента: среда и эталон живут в
отдельном серверном процессе (`python -m auditenv serve`), у клиента тот же API.

```python
from auditenv.serve import AuditEnvClient
with AuditEnvClient(mode="train") as env:
    obs, info = env.reset(seed=7, config="dev-mixed")
    obs, reward, terminated, truncated, info = env.step({"tool": "list_records", "args": {"table": "ledger"}})
```

Тест `test_client_replays_trajectories_byte_identical` проигрывает записанные траектории через
клиента и сравнивает байты с in‑process средой.

## Пример

[`examples/minimal_agent.py`](../examples/minimal_agent.py) — около 35 строк: листает платежи, счета
и проводки, находит платежи со ссылками на счета, оставшиеся на 2400, и отправляет выводы.
