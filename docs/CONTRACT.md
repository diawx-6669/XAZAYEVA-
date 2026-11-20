# Контракт среды (машиночитаемая версия — [`contract.json`](../contract.json), в коде — `env.spec`)

Тест `tests/test_contract_json.py` сверяет каждое число и каждую трактовку из `contract.json` с
константами кода **и** с реальным поведением среды. Изменить поведение, не обновив контракт, нельзя.

| Вопрос | Трактовка | Где в коде |
|---|---|---|
| Сколько шагов? | 100, включая `submit`; ошибка тоже тратит шаг | `env/env.py::MAX_STEPS` |
| `inspection_steps` при `submit` | шаги **до** submit, сам submit не считается | `env.py::_finish` |
| `inspection_steps` при обрыве по шагам | 100 | `env.py::_finish` |
| `inspection_steps` при тайм‑ауте | сколько шагов успели сделать; запоздавшее действие не выполняется и не оценивается | `env.py::step` |
| Что оценивается при `truncated` | пустой ответ | `grader/core.py::grade` |
| Обрыв на чистой книге | 2·1 − 1 − 0.002·100 = **0.8** | `grader/reward.py` |
| `limit` > 50 или < 1 | `bad_args` | `env/tools.py::list_records` |
| Пустая ячейка CSV | `null` | `generator/export.py::parse_files` |
| Формы `submit` | вложенная `{findings: {episode_id, findings}}` и плоская `{episode_id, findings}` | `env.py::submission_from_args` |
| Неверный `submit` (нет/пустые/кривые args) | `terminated`, награда −1, агенту — только `{"submitted": true}`, причина — в журнале оценщика | `env.py::step`, `grader/core.py` |
| Чужой `episode_id` | −1, `terminated` | `grader/schema.py` |
| Шаг после конца | `episode_over`, награда 0, итог не меняется | `env.py::step` |
| Нет такого ID / ID из другой таблицы | одинаково `not_found` | `env/tools.py` |
| Коды ошибок | `unknown_tool, bad_args, not_found, invalid_cursor, calc_error, episode_over` — и ничего больше | `env/errors.py` |
| Награда по ходу | 0 | `env.py::step` |
| Режим `eval` | награда 0, `info = {}`, итог только в `grader_log.jsonl` | `env.py::_finish` |
| `reset()` до конца эпизода | эпизод пишется в журнал как `abandoned` | `env.py::reset` |
| `reset()` без seed | seed 0 (детерминированно); seed только `int` | `env.py::_check_seed` |
| Допуск по сумме | из `config.tolerance_minor` → `truth.json` → оценщик; по умолчанию 1; число есть в тексте задачи | `grader/core.py` |
| Лимиты findings | ≤ 30 выводов, ≤ 10 ID доказательств, ≤ 1000 символов объяснения | `schemas/findings.schema.json` |
