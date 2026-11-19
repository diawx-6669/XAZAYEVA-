# AuditEnv self-check

Эпизоды: 20 (5 clean-only, 5 interaction-heavy, 10 dev-mixed). Время: 7.5 c.

## Табло

| Блок | Пройдено | Баллы |
|---|---|---|
| Контракт и изоляция | 20/20 | 25.0 / 25 |
| Данные и эталон | 20/20 | 25.0 / 25 |
| Надёжность награды | 20/20 | 25.0 / 25 |
| Воспроизводимость и обобщение | 20/20 | 15.0 / 15 |
| **Итого (без «Инженерии», 10 баллов оценивает жюри)** | | **90.0 / 90** |

### Контракт и изоляция

- PASS — reset() shape and first observation
- PASS — step() 5-tuple, reward 0 while exploring
- PASS — observations follow observation.schema.json
- PASS — page limit 50 enforced
- PASS — cursors stable, full pagination exact
- PASS — foreign/garbled cursors rejected
- PASS — unknown tool -> unknown_tool, step spent
- PASS — unknown / other-table ID -> same not_found
- PASS — malformed actions -> bad_args
- PASS — 100 steps without submit -> truncated, empty answer
- PASS — submit on step 100 allowed
- PASS — time limit -> truncated
- PASS — step after end -> episode_over, result frozen
- PASS — calculator rejects code/power/names/long/div0/deep
- PASS — calculator exact decimal arithmetic
- PASS — eval mode: reward 0, info {}, result only in grader log
- PASS — two env instances do not interfere
- PASS — reset() isolates episode state
- PASS — invalid findings -> -1, terminated, logged
- PASS — leakscan clean on all trajectories; records read-only

### Данные и эталон

- PASS — clean-only#9001 (0 issues)
- PASS — clean-only#9002 (0 issues)
- PASS — clean-only#9003 (0 issues)
- PASS — clean-only#9004 (0 issues)
- PASS — clean-only#9005 (0 issues)
- PASS — interaction-heavy#9006 (5 issues)
- PASS — interaction-heavy#9007 (3 issues)
- PASS — interaction-heavy#9008 (3 issues)
- PASS — interaction-heavy#9009 (5 issues)
- PASS — interaction-heavy#9010 (4 issues)
- PASS — dev-mixed#9011 (4 issues)
- PASS — dev-mixed#9012 (1 issues)
- PASS — dev-mixed#9013 (4 issues)
- PASS — dev-mixed#9014 (3 issues)
- PASS — dev-mixed#9015 (4 issues)
- PASS — dev-mixed#9016 (0 issues)
- PASS — dev-mixed#9017 (2 issues)
- PASS — dev-mixed#9018 (3 issues)
- PASS — dev-mixed#9019 (1 issues)
- PASS — dev-mixed#9020 (1 issues)

### Надёжность награды

- PASS — oracle answer beats silence on erroneous books
- PASS — silence beats false accusations on clean books
- PASS — twins attack (x30) gains nothing
- PASS — duplicated findings never add reward
- PASS — flag_all scores <= -0.5 everywhere
- PASS — all types x all docs scores <= 0
- PASS — 10 vs 50 steps differ by exactly 0.08
- PASS — explanation text has no effect
- PASS — persuasive wrong answer gets no TP
- PASS — guessed IDs get no TP
- PASS — evidence spam without a valid set gets no TP
- PASS — wrong currency gets no TP
- PASS — type brute force < oracle
- PASS — amount brute force < oracle
- PASS — malformed findings -> -1
- PASS — foreign episode_id -> -1
- PASS — finding order does not change F1
- PASS — re-submission is ignored
- PASS — truncation grades an empty answer
- PASS — tolerance: +-1 matches, +-2 does not

### Воспроизводимость и обобщение

- PASS — clean-only#9001 twin
- PASS — clean-only#9002 twin
- PASS — clean-only#9003 twin
- PASS — clean-only#9004 twin
- PASS — clean-only#9005 twin
- PASS — interaction-heavy#9006 twin
- PASS — interaction-heavy#9007 twin
- PASS — interaction-heavy#9008 twin
- PASS — interaction-heavy#9009 twin
- PASS — interaction-heavy#9010 twin
- PASS — dev-mixed#9011 twin
- PASS — dev-mixed#9012 twin
- PASS — dev-mixed#9013 twin
- PASS — dev-mixed#9014 twin
- PASS — dev-mixed#9015 twin
- PASS — dev-mixed#9016 twin
- PASS — dev-mixed#9017 twin
- PASS — dev-mixed#9018 twin
- PASS — dev-mixed#9019 twin
- PASS — dev-mixed#9020 twin

## Диагностика политик (режим eval, средние по 20 эпизодам)

| Политика | P | R | F1 | Возврат | Возврат (эксп.) | Шаги | Время, мс (ср/макс) | Агент видел награду |
|---|---|---|---|---|---|---|---|---|
| random_explorer | 0.000 | 0.000 | 0.300 | -0.417 | -0.417 | 30.0 | 70 / 102 | нет |
| simple_reconcile | 0.612 | 0.648 | 0.667 | 0.312 | 0.312 | 14.2 | 68 / 79 | нет |
| flag_all | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | 3.0 | 65 / 95 | нет |
| oracle | 0.700 | 0.700 | 1.000 | 1.000 | -0.400 | 1.0 | 2 / 2 | нет |
| attack:twins | 0.023 | 0.312 | 0.042 | -0.915 | -1.000 | 1.0 | 4 / 4 | нет |
| attack:type_bruteforce | 0.175 | 0.700 | 0.580 | 0.160 | -0.400 | 1.0 | 3 / 5 | нет |
| attack:amount_bruteforce | 0.068 | 0.610 | 0.422 | -0.156 | -0.400 | 1.0 | 4 / 4 | нет |
| attack:guess_ids | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | 1.0 | 3 / 4 | нет |
| attack:evidence_spam | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | 1.0 | 3 / 4 | нет |
| attack:junk_explanation | 0.700 | 0.700 | 1.000 | 1.000 | -0.400 | 1.0 | 4 / 10 | нет |
| attack:persuasive_wrong | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | 1.0 | 3 / 4 | нет |
| attack:wrong_currency | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | 1.0 | 3 / 4 | нет |
| attack:all_types_all_docs | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | 1.0 | 4 / 5 | нет |
| attack:empty | 0.000 | 0.000 | 0.300 | -0.400 | -0.400 | 1.0 | 3 / 4 | нет |

## Разбор сбоев simple_reconcile

| Тип ошибки | Найдено / всего |
|---|---|
| duplicate_invoice | 9 / 9 |
| fx_rate | 7 / 11 |
| payment_allocation | 14 / 14 |
| period_cutoff | 9 / 9 |

Коды причин ложных выводов: `ids_mismatch`: 3, `unmatched`: 7, `wrong_type`: 2
