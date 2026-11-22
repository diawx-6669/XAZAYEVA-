# Статистика записанных траекторий

Сгенерировано `python tools/trajectory_stats.py` из `trajectories/trajectories.jsonl` (1201 строк, 64 прогонов).
Награда — терминальная в режиме train (как записана в траектории).

| Политика | Прогонов | Шагов: медиана / макс | list_records | get_record | get_document | calculator | submit | Ошибки инструментов | Как закончился | Средняя награда |
|---|---|---|---|---|---|---|---|---|---|---|
| `flag_all` | 20 | 3 / 3 | 40 | 0 | 0 | 0 | 20 | — | submitted 20 | -1.000 |
| `hung` | 2 | 0 / 0 | 0 | 0 | 0 | 0 | 0 | `episode_over` 2 | truncated: policy_unresponsive 2 | -0.100 |
| `random_explorer` | 20 | 30 / 30 | 294 | 122 | 20 | 102 | 20 | `unknown_tool` 42, `not_found` 38 | submitted 20 | -0.515 |
| `simple_reconcile` | 20 | 13.5 / 16 | 235 | 20 | 0 | 0 | 20 | — | submitted 20 | +0.177 |
| `step_burner` | 2 | 100 / 100 | 200 | 0 | 0 | 0 | 0 | — | truncated: max_steps 2 | -0.100 |

## Какие таблицы листают

| Политика | ledger | invoices | payments | fx |
|---|---|---|---|---|
| `flag_all` | 0 | 20 | 20 | 0 |
| `random_explorer` | 118 | 78 | 22 | 76 |
| `simple_reconcile` | 132 | 20 | 20 | 63 |
| `step_burner` | 200 | 0 | 0 | 0 |

Наблюдения: честный `simple_reconcile` читает все таблицы постранично и не делает ни одной ошибки инструмента;
`random_explorer` тратит шаги и в том числе ошибается (каждая ошибка стоит шаг); `step_burner` и `hung` записаны
специально — это контракт обрыва (100 шагов → `max_steps`, зависание → `policy_unresponsive`).
