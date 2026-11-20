# AuditEnv self-check

commit `03dfa5fcfd7d` · env 0.1.0 · auditenv-gen-0.1.0 · Python 3.11.18 · pip 24.0 · Linux x86_64

Хеши конфигов: `clean-only` b3ea7789592542fd, `dev-global` 901a6f99473a48ad, `dev-mixed` 2435d9d9eff18731, `interaction-heavy` 69494e59920a9b92, `stress` 7dd64db6b1aeac85, `train-easy` 58e3dda93da800ba, `train-global` 700ad883b68e9fbf

Эпизоды: 20 (5 clean-only, 5 interaction-heavy, 5 dev-mixed, 5 dev-global). Всё до раздела «Замеры времени» детерминировано: повторный прогон на том же коммите даёт те же байты.

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
- PASS — invalid findings / malformed submit -> -1, terminated, logged; flat form ok
- PASS — leakscan clean on all trajectories; records read-only

### Данные и эталон

- PASS — clean-only#9001 (0 issues)
- PASS — clean-only#9002 (0 issues)
- PASS — clean-only#9003 (0 issues)
- PASS — clean-only#9004 (0 issues)
- PASS — clean-only#9005 (0 issues)
- PASS — interaction-heavy#9006 (3 issues)
- PASS — interaction-heavy#9007 (3 issues)
- PASS — interaction-heavy#9008 (3 issues)
- PASS — interaction-heavy#9009 (5 issues)
- PASS — interaction-heavy#9010 (2 issues)
- PASS — dev-mixed#9011 (4 issues)
- PASS — dev-mixed#9012 (4 issues)
- PASS — dev-mixed#9013 (1 issues)
- PASS — dev-mixed#9014 (3 issues)
- PASS — dev-mixed#9015 (0 issues)
- PASS — dev-global#9016 (1 issues)
- PASS — dev-global#9017 (4 issues)
- PASS — dev-global#9018 (3 issues)
- PASS — dev-global#9019 (1 issues)
- PASS — dev-global#9020 (0 issues)

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
- PASS — dev-global#9016 twin
- PASS — dev-global#9017 twin
- PASS — dev-global#9018 twin
- PASS — dev-global#9019 twin
- PASS — dev-global#9020 twin

## Диагностика политик (режим eval, 20 эпизодов)

P, R — макро (среднее по эпизодам, где величина определена); микро — ΣTP/ΣFP/ΣFN по всем эпизодам; «n/a» — не определено (нет выводов / нет ошибок). Возврат отдельно на чистых и ошибочных книгах.

| Политика | P | R | F1 | микро P | микро R | микро F1 | Возврат | на чистых | на ошибочных | Возврат (эксп.) | Шаги | Агент видел награду |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random_explorer | n/a | 0.000 | 0.350 | n/a | 0.000 | 0.000 | -0.320 | 0.942 | -1.000 | -0.320 | 30.0 | нет |
| simple_reconcile | 0.488 | 0.888 | 0.517 | 0.604 | 0.865 | 0.711 | 0.017 | -1.000 | 0.565 | 0.017 | 13.9 | нет |
| flag_all | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | -1.000 | -1.000 | 4.0 | нет |
| oracle | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | -0.300 | 1.0 | нет |
| oracle_observing | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.989 | 1.000 | 0.983 | 0.989 | 6.4 | нет |
| attack:twins | 0.022 | 0.471 | 0.040 | 0.022 | 0.351 | 0.041 | -0.921 | -1.000 | -0.878 | -1.000 | 1.0 | нет |
| attack:type_bruteforce | 0.250 | 1.000 | 0.610 | 0.250 | 1.000 | 0.400 | 0.220 | 1.000 | -0.200 | -0.300 | 1.0 | нет |
| attack:amount_bruteforce | 0.097 | 0.912 | 0.464 | 0.098 | 0.865 | 0.177 | -0.072 | 1.000 | -0.650 | -0.300 | 1.0 | нет |
| attack:guess_ids | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | -1.000 | -1.000 | 1.0 | нет |
| attack:evidence_spam | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | -1.000 | -1.000 | 1.0 | нет |
| attack:junk_explanation | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | -0.300 | 1.0 | нет |
| attack:persuasive_wrong | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | -1.000 | -1.000 | 1.0 | нет |
| attack:wrong_currency | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | -1.000 | -1.000 | 1.0 | нет |
| attack:all_types_all_docs | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | -1.000 | -1.000 | -1.000 | -1.000 | 1.0 | нет |
| attack:empty | n/a | 0.000 | 0.350 | n/a | 0.000 | 0.000 | -0.300 | 1.000 | -1.000 | -0.300 | 1.0 | нет |

## Разбор сбоев simple_reconcile

| Тип ошибки | Найдено / всего |
|---|---|
| duplicate_invoice | 11 / 11 |
| fx_rate | 6 / 11 |
| payment_allocation | 6 / 6 |
| period_cutoff | 9 / 9 |

Коды причин ложных выводов: `ids_mismatch`: 5, `unmatched`: 14, `wrong_type`: 2

Журнал оценщика `reports/grader_log.jsonl`: цепочка хешей, голова `b296e9465f43fad9b7949475a08c0563711d1c74586b20d9602923a54a0ee997` (проверка: `python -m auditenv verify-log`).

## Замеры времени (недетерминированно, зависит от машины)

Полный self-check: 9.8 c.

| Политика | ср, мс | p50, мс | p95, мс | макс, мс |
|---|---|---|---|---|
| random_explorer | 90 | 87 | 108 | 115 |
| simple_reconcile | 88 | 84 | 118 | 120 |
| flag_all | 89 | 82 | 107 | 112 |
| oracle | 2 | 2 | 2 | 2 |
| oracle_observing | 2 | 2 | 2 | 10 |
| attack:twins | 5 | 5 | 5 | 5 |
| attack:type_bruteforce | 3 | 3 | 4 | 4 |
| attack:amount_bruteforce | 4 | 3 | 5 | 5 |
| attack:guess_ids | 3 | 3 | 4 | 5 |
| attack:evidence_spam | 3 | 3 | 3 | 4 |
| attack:junk_explanation | 3 | 3 | 3 | 3 |
| attack:persuasive_wrong | 3 | 3 | 3 | 11 |
| attack:wrong_currency | 3 | 3 | 3 | 4 |
| attack:all_types_all_docs | 5 | 5 | 5 | 5 |
| attack:empty | 3 | 3 | 3 | 3 |
