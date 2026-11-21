# Мутационное тестирование оценщика

Генерируется `make mutation` (`python tools/mutation_test.py`), в `make check` не входит. Каждая мутация —
одна намеренная ошибка в коде оценщика (точная замена текста); после неё прогоняются быстрые тесты
(`pytest -m "not slow" -x`, сначала тесты оценщика). «Убита» — какой‑то тест упал; в таблице — первый
упавший тест, **подтверждённый** повторным запуском этого теста отдельно на том же мутанте (тест, который
отдельно проходит, считается флейком от нагрузки, исключается, и прогон продолжается).
Выжившая мутация означает, что тесты не отличают баг от правильного оценщика.

**Итог: 23/23 мутаций убито** (100 %). Базовый прогон без мутаций зелёный (64 с); всё вместе — 83 с.

## История

* Раунд 3, первый прогон: 20/22 убито. Выжили M05 (тип не проверяется: перебор 4 типов всё равно даёт TP = 1, FP = 3, поэтому тесты не отличали баг) и M08 (жадное паросочетание вместо максимального: `test_tie_break_smallest_issue_then_index` заявлял эту проверку, но его пример жадный алгоритм тоже решает). M06 был убит только косвенно, через сканер совпадений генератора; M18 оказался синтаксически неверным мутантом (исправлен, теперь инструмент проверяет компиляцию каждого мутанта). Дописаны прямые тесты: `tests/test_mutation_kills.py`.
* Второй прогон: 21/22. Исправленный M18 выжил: проверка `type(...) is int` в `grader/schema.py` дублирует строгость `jsonschema_lite` ("integer" не принимает 5.0), поэтому ни один тест не видел второй слой отдельно. Добавлен тест `test_grader_int_check_works_even_if_the_schema_validator_accepted_floats` (валидатор подменён на «принимаю всё») и мутация M23 для самого валидатора.

## Текущий прогон

| # | Файл | Мутация | Итог | Какой тест поймал |
|---|---|---|---|---|
| M01 | `auditenv/grader/matcher.py` | amount tolerance: <= becomes < (an exact-boundary claim is rejected) | убита | `tests/test_reward.py::test_tolerance_boundary` |
| M02 | `auditenv/grader/matcher.py` | currency is not checked | убита | `tests/test_reward.py::test_wrong_currency_is_fp` |
| M03 | `auditenv/grader/matcher.py` | evidence is not checked | убита | `tests/test_reward.py::test_flag_all_is_bad` |
| M04 | `auditenv/grader/matcher.py` | one ID of an evidence set is enough (subset -> intersection) | убита | `tests/test_reward.py::test_partial_evidence_is_fp` |
| M05 | `auditenv/grader/matcher.py` | type is not checked | убита | `tests/test_mutation_kills.py::test_lone_wrong_type_is_fp_with_reason_wrong_type` |
| M06 | `auditenv/grader/matcher.py` | affected_ids: a superset is accepted instead of exact equality | убита | `tests/test_mutation_kills.py::test_superset_of_affected_ids_is_fp` |
| M07 | `auditenv/grader/matcher.py` | no one-to-one matching: every repeat of a correct finding is a TP | убита | `tests/test_reward.py::test_duplicates_give_no_gain` |
| M08 | `auditenv/grader/matcher.py` | greedy matching instead of maximum matching (no augmenting paths) | убита | `tests/test_mutation_kills.py::test_matching_is_maximum_not_greedy` |
| M09 | `auditenv/grader/matcher.py` | tie-break: the LARGER issue_id wins instead of the smaller | убита | `tests/test_reward.py::test_tie_break_smallest_issue_then_index` |
| M10 | `auditenv/grader/normalize.py` | IDs are not stripped of whitespace | убита | `tests/test_reward.py::test_currency_and_ids_are_normalized` |
| M11 | `auditenv/grader/normalize.py` | repeated IDs are not de-duplicated | убита | `tests/test_reward.py::test_currency_and_ids_are_normalized` |
| M12 | `auditenv/grader/normalize.py` | currency is not upper-cased | убита | `tests/test_reward.py::test_currency_and_ids_are_normalized` |
| M13 | `auditenv/grader/normalize.py` | IDs are case-folded (the contract says case is preserved) | убита | `tests/test_reward.py::test_duplicates_give_no_gain` |
| M14 | `auditenv/grader/reward.py` | F1 = 0 when truth and findings are both empty | убита | `tests/test_reward.py::test_silence_beats_any_accusation_on_clean` |
| M15 | `auditenv/grader/reward.py` | F1 = 1 when truth is empty but findings are not (accusing a clean book is free) | убита | `tests/test_reward.py::test_silence_beats_any_accusation_on_clean` |
| M16 | `auditenv/grader/reward.py` | step cost 0.001 instead of 0.002 | убита | `tests/test_reward.py::test_step_cost_10_vs_50_is_exactly_0_08` |
| M17 | `auditenv/grader/reward.py` | reward is not clipped to [-1, 1] | убита | `tests/test_reward.py::test_property_reward_bounded` |
| M18 | `auditenv/grader/schema.py` | float amounts (5.0) are accepted | убита | `tests/test_mutation_kills.py::test_grader_int_check_works_even_if_the_schema_validator_accepted_floats` |
| M19 | `auditenv/grader/schema.py` | a foreign episode_id is accepted | убита | `tests/test_contract.py::test_invalid_structure_minus_one[findings3]` |
| M20 | `auditenv/grader/core.py` | a truncated episode is graded on the agent's findings instead of the empty answer | убита | `tests/test_contract.py::test_timeout_on_clean_book_is_charged_full_budget` |
| M21 | `schemas/findings.schema.json` | the 30-findings cap is lifted | убита | `tests/test_reward.py::test_bad_json_is_minus_one` |
| M23 | `auditenv/jsonschema_lite.py` | schema validator: "integer" accepts 5.0 and True | убита | `tests/test_jsonschema_lite.py::test_invalid[value2-type]` |
| M22 | `auditenv/grader/core.py` | experimental reward: evidence the agent never saw still counts | убита | `tests/test_reward.py::test_experimental_reward_requires_seen_evidence` |

Флейки, исключённые при перепроверке: нет


Время по мутациям (с): M01 1, M02 2, M03 2, M04 2, M05 6, M06 6, M07 1, M08 5, M09 1, M10 1, M11 1, M12 2, M13 2, M14 1, M15 1, M16 2, M17 2, M18 6, M19 2, M20 2, M21 1, M23 6, M22 1
