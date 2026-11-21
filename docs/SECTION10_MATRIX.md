# Матрица: разделы 05, 10 и блокеры кейса → тесты

Сгенерировано `python tools/section10_matrix.py`; тест `tests/test_round4_section10.py` проверяет, что каждый
названный тест существует, и у каждой строки есть хотя бы один тест. Повторить строку: `python -m pytest -q <тест>`.

## 10 · Контракт и изоляция (25)

| Что проверяется | Тесты | Где ещё |
|---|---|---|
| reset / step: формы | `tests/test_contract.py::test_reset_shape`<br>`tests/test_contract.py::test_step_shape_and_zero_reward` | табло «Контракт» |
| схемы наблюдений и артефактов | `tests/test_batch_c.py::test_committed_artefacts_match_schemas`<br>`tests/test_batch_c.py::test_info_schema`<br>`tests/test_round4_contract_pin.py::test_contract_matches_pin_or_schema_version_was_bumped` | `check-schemas` |
| лимиты: 50 строк, 100 шагов, 60 с | `tests/test_contract.py::test_page_limit_50`<br>`tests/test_contract.py::test_100_steps_truncated`<br>`tests/test_contract.py::test_timeout_truncates` |  |
| завершение: submit, шаг после конца | `tests/test_contract.py::test_submit_on_step_100_is_allowed`<br>`tests/test_contract.py::test_step_after_end` |  |
| неверный ввод: инструмент, аргументы, курсоры, калькулятор | `tests/test_contract.py::test_unknown_tool_and_ids_consume_steps`<br>`tests/test_contract.py::test_bad_args`<br>`tests/test_contract.py::test_cursor_from_other_episode_or_table`<br>`tests/test_calculator.py::test_rejected` | `tests/test_fuzz.py` |
| отсутствие утечек | `tests/test_leaks.py::test_committed_trajectories_are_clean`<br>`tests/test_isolation.py::test_closed_run_hunter_finds_nothing`<br>`tests/test_conceal.py::test_agent_sees_no_seed_config_paths_or_salt`<br>`tests/test_round4_no_abs_paths.py::test_no_absolute_paths` | `leakscan` |

## 10 · Данные и эталон (25)

| Что проверяется | Тесты | Где ещё |
|---|---|---|
| бухгалтерские равенства до внесения ошибки | `tests/test_data.py::test_clean_book_invariants` | табло «Данные» |
| объявленное расхождение после | `tests/test_data.py::test_error_breaks_exactly_its_invariant`<br>`tests/test_batch_c.py::test_verify_provenance`<br>`tests/test_round4_explain.py::test_amounts_recomputed_from_snapshots_on_all_open_episodes` | `verify-provenance` |
| независимая достаточность доказательств | `tests/test_data.py::test_every_evidence_id_reachable_through_tools`<br>`tests/test_batch_c.py::test_independent_verifier_agrees_and_imports_nothing`<br>`tests/test_batch_c.py::test_evidence_sets_are_minimal_and_alternatives_exist` | `verify-independent` (540 эпизодов) |
| противоречивые данные не считаются сложностью | `tests/test_batch_c.py::test_lint_only_truth_explains_implausibility` | `lint` |
| чистые книги: эталон пуст, решатель молчит | `tests/test_data.py::test_clean_episodes_have_empty_truth_and_solver_finds_nothing` |  |

## 10 · Надёжность награды (25) и 05 · «Тесты должны показать»

| Что проверяется | Тесты | Где ещё |
|---|---|---|
| полный верный ответ лучше молчания на ошибочных | `tests/test_reward.py::test_oracle_beats_silence_on_erroneous` |  |
| молчание лучше ложных обвинений на чистых | `tests/test_reward.py::test_silence_beats_any_accusation_on_clean` |  |
| дубли не дают выгоды | `tests/test_reward.py::test_duplicates_give_no_gain` |  |
| пометка всех строк / типов — плохо | `tests/test_reward.py::test_flag_all_is_bad` |  |
| экономия шагов лишь немного различает равные ответы | `tests/test_reward.py::test_step_cost_10_vs_50_is_exactly_0_08`<br>`tests/test_reward_exhaustive.py::test_reward_exhaustive_small` | `reports/step_cost.md` |
| сопоставление: допуск, ничьи, порядок | `tests/test_reward.py::test_tolerance_boundary`<br>`tests/test_reward.py::test_tie_break_smallest_issue_then_index`<br>`tests/test_reward.py::test_finding_order_irrelevant` | `reports/tolerance.md` |
| угаданные ID, неподтверждённые доказательства | `tests/test_reward.py::test_guessed_id_without_evidence_is_fp`<br>`tests/test_reward.py::test_partial_evidence_is_fp` | `reports/ablation_evidence.md` |
| валюты | `tests/test_reward.py::test_wrong_currency_is_fp`<br>`tests/test_reward.py::test_currency_and_ids_are_normalized` |  |
| повторная отправка, неверный ввод, тайм‑аут | `tests/test_contract.py::test_step_after_end`<br>`tests/test_reward.py::test_bad_json_is_minus_one`<br>`tests/test_contract.py::test_timeout_on_clean_book_is_charged_full_budget` |  |
| атакующие ответы | `tests/test_reward.py::test_attacks_never_beat_oracle`<br>`tests/test_reward.py::test_attacks_score_badly`<br>`tests/test_exploit_search.py::test_cem_best_below_silence_and_simple_reconcile` | `site/attacks.html` |
| награда от полей и доказательств, не от текста | `tests/test_reward.py::test_explanation_has_no_effect` |  |
| экспериментальная награда отдельно от общей | `tests/test_reward.py::test_experimental_reward_requires_seen_evidence` |  |

## 10 · Воспроизводимость и обобщение (15)

| Что проверяется | Тесты | Где ещё |
|---|---|---|
| повтор seed / действий точен | `tests/test_repro.py::test_same_seed_same_bytes`<br>`tests/test_repro.py::test_same_actions_same_trajectory_and_rewards`<br>`tests/test_batch_c.py::test_bytes_identical_across_interpreters_hashseed_tz_lang_cwd` | `replay`, `make repro-cross` |
| перестановка и смена ID сохраняют ответ oracle и награду | `tests/test_repro.py::test_transform_preserves_oracle_and_f1`<br>`tests/test_round3.py::test_jury_pairs_command_equal_on_opaque_twins` | табло «Воспроизводимость» |

## 10 · Инженерия и объяснение (10)

| Что проверяется | Тесты | Где ещё |
|---|---|---|
| запуск одной командой | `tests/test_docs_examples.py::test_runnable_blocks_work` | `make check`, `make docker-check` |
| версии конфигураций | `tests/test_configs_lock.py::test_lock_is_current`<br>`tests/test_configs_lock.py::test_content_change_without_version_bump_fails`<br>`tests/test_round4_config.py::test_config_reference_up_to_date` | `configs/LOCK.json` |
| журналы траекторий | `tests/test_batch_c.py::test_trajectories_record_step_burner_and_hung`<br>`tests/test_batch_c.py::test_log_chain_detects_edits` | `reports/trajectory_stats.md` |
| измеренный разбор сбоев | `tests/test_round4_cards.py::test_episode_cards_up_to_date` | `docs/FAILURES.md`, `reports/difficulty.md` |
| честные ограничения | `tests/test_round4_links.py::test_relative_links_resolve` | `docs/LIMITATIONS.md`, `docs-check` |

## 10 · Блокеры оценивания

| Что проверяется | Тесты | Где ещё |
|---|---|---|
| утечка закрытых данных | `tests/test_isolation.py::test_closed_run_hunter_finds_nothing`<br>`tests/test_leaks.py::test_seed_salt_blocks_seed_bruteforce`<br>`tests/test_guards.py::test_agent_cannot_read_parent_environ_salt` |  |
| запись в оценщик | `tests/test_batch_c.py::test_writer_attack_changes_nothing`<br>`tests/test_batch_c.py::test_grader_digest_detects_tampered_truth` | `verify-log` |
| реальные финансовые данные | `tests/test_round4_pii.py::test_generated_episodes_contain_no_real_data`<br>`tests/test_round4_pii.py::test_scanner_finds_planted_data` | `make pii-scan`, `docs/SAFETY.md` |
| неработающее ядро | `tests/test_config_fuzz.py::test_config_space_fuzz`<br>`tests/test_fuzz.py::test_fuzz_actions` | `make check` |
| диагностика P, R, F1, возврат, шаги, время | `tests/test_runner.py::test_eval_mode_child_never_sees_reward` | `reports/selfcheck.md` |
