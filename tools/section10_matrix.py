"""B25: docs/SECTION10_MATRIX.md - every check named in sections 05, 06, 10 and 12 of the case -> the tests and
reports that cover it. tests/test_round4_section10.py verifies that every cited test function exists and that
every row has at least one test; the doc is regenerated from the table below.

    python tools/section10_matrix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

C, R, D, B, V = "tests/test_contract.py", "tests/test_reward.py", "tests/test_data.py", "tests/test_batch_c.py", "tests/test_repro.py"
MATRIX = [
    ("10 · Контракт и изоляция (25)", [
        ("reset / step: формы", [f"{C}::test_reset_shape", f"{C}::test_step_shape_and_zero_reward"], "табло «Контракт»"),
        ("схемы наблюдений и артефактов", [f"{B}::test_committed_artefacts_match_schemas", f"{B}::test_info_schema",
                                           "tests/test_round4_contract_pin.py::test_contract_matches_pin_or_schema_version_was_bumped"], "`check-schemas`"),
        ("лимиты: 50 строк, 100 шагов, 60 с", [f"{C}::test_page_limit_50", f"{C}::test_100_steps_truncated", f"{C}::test_timeout_truncates"], ""),
        ("завершение: submit, шаг после конца", [f"{C}::test_submit_on_step_100_is_allowed", f"{C}::test_step_after_end"], ""),
        ("неверный ввод: инструмент, аргументы, курсоры, калькулятор", [f"{C}::test_unknown_tool_and_ids_consume_steps", f"{C}::test_bad_args",
                                                                       f"{C}::test_cursor_from_other_episode_or_table", "tests/test_calculator.py::test_rejected"], "`tests/test_fuzz.py`"),
        ("отсутствие утечек", ["tests/test_leaks.py::test_committed_trajectories_are_clean", "tests/test_isolation.py::test_closed_run_hunter_finds_nothing",
                               "tests/test_conceal.py::test_agent_sees_no_seed_config_paths_or_salt",
                               "tests/test_round4_no_abs_paths.py::test_no_absolute_paths"], "`leakscan`"),
    ]),
    ("10 · Данные и эталон (25)", [
        ("бухгалтерские равенства до внесения ошибки", [f"{D}::test_clean_book_invariants"], "табло «Данные»"),
        ("объявленное расхождение после", [f"{D}::test_error_breaks_exactly_its_invariant", f"{B}::test_verify_provenance",
                                           "tests/test_round4_explain.py::test_amounts_recomputed_from_snapshots_on_all_open_episodes"], "`verify-provenance`"),
        ("независимая достаточность доказательств", [f"{D}::test_every_evidence_id_reachable_through_tools",
                                                    f"{B}::test_independent_verifier_agrees_and_imports_nothing",
                                                    f"{B}::test_evidence_sets_are_minimal_and_alternatives_exist"], "`verify-independent` (540 эпизодов)"),
        ("противоречивые данные не считаются сложностью", [f"{B}::test_lint_only_truth_explains_implausibility"], "`lint`"),
        ("чистые книги: эталон пуст, решатель молчит", [f"{D}::test_clean_episodes_have_empty_truth_and_solver_finds_nothing"], ""),
    ]),
    ("10 · Надёжность награды (25) и 05 · «Тесты должны показать»", [
        ("полный верный ответ лучше молчания на ошибочных", [f"{R}::test_oracle_beats_silence_on_erroneous"], ""),
        ("молчание лучше ложных обвинений на чистых", [f"{R}::test_silence_beats_any_accusation_on_clean"], ""),
        ("дубли не дают выгоды", [f"{R}::test_duplicates_give_no_gain"], ""),
        ("пометка всех строк / типов — плохо", [f"{R}::test_flag_all_is_bad"], ""),
        ("экономия шагов лишь немного различает равные ответы", [f"{R}::test_step_cost_10_vs_50_is_exactly_0_08",
                                                                "tests/test_reward_exhaustive.py::test_reward_exhaustive_small"], "`reports/step_cost.md`"),
        ("сопоставление: допуск, ничьи, порядок", [f"{R}::test_tolerance_boundary", f"{R}::test_tie_break_smallest_issue_then_index",
                                                  f"{R}::test_finding_order_irrelevant"], "`reports/tolerance.md`"),
        ("угаданные ID, неподтверждённые доказательства", [f"{R}::test_guessed_id_without_evidence_is_fp", f"{R}::test_partial_evidence_is_fp"],
         "`reports/ablation_evidence.md`"),
        ("валюты", [f"{R}::test_wrong_currency_is_fp", f"{R}::test_currency_and_ids_are_normalized"], ""),
        ("повторная отправка, неверный ввод, тайм‑аут", [f"{C}::test_step_after_end", f"{R}::test_bad_json_is_minus_one",
                                                        f"{C}::test_timeout_on_clean_book_is_charged_full_budget"], ""),
        ("атакующие ответы", [f"{R}::test_attacks_never_beat_oracle", f"{R}::test_attacks_score_badly",
                              "tests/test_exploit_search.py::test_cem_best_below_silence_and_simple_reconcile"], "`site/attacks.html`"),
        ("награда от полей и доказательств, не от текста", [f"{R}::test_explanation_has_no_effect"], ""),
        ("экспериментальная награда отдельно от общей", [f"{R}::test_experimental_reward_requires_seen_evidence"], ""),
    ]),
    ("10 · Воспроизводимость и обобщение (15)", [
        ("повтор seed / действий точен", [f"{V}::test_same_seed_same_bytes", f"{V}::test_same_actions_same_trajectory_and_rewards",
                                          f"{B}::test_bytes_identical_across_interpreters_hashseed_tz_lang_cwd"], "`replay`, `make repro-cross`"),
        ("перестановка и смена ID сохраняют ответ oracle и награду", [f"{V}::test_transform_preserves_oracle_and_f1",
                                                                     "tests/test_round3.py::test_jury_pairs_command_equal_on_opaque_twins"], "табло «Воспроизводимость»"),
    ]),
    ("10 · Инженерия и объяснение (10)", [
        ("запуск одной командой", ["tests/test_docs_examples.py::test_runnable_blocks_work"], "`make check`, `make docker-check`"),
        ("версии конфигураций", ["tests/test_configs_lock.py::test_lock_is_current", "tests/test_configs_lock.py::test_content_change_without_version_bump_fails", "tests/test_round4_config.py::test_config_reference_up_to_date"], "`configs/LOCK.json`"),
        ("журналы траекторий", [f"{B}::test_trajectories_record_step_burner_and_hung", f"{B}::test_log_chain_detects_edits"],
         "`reports/trajectory_stats.md`"),
        ("измеренный разбор сбоев", ["tests/test_round4_cards.py::test_episode_cards_up_to_date"], "`docs/FAILURES.md`, `reports/difficulty.md`"),
        ("честные ограничения", ["tests/test_round4_links.py::test_relative_links_resolve"], "`docs/LIMITATIONS.md`, `docs-check`"),
    ]),
    ("10 · Блокеры оценивания", [
        ("утечка закрытых данных", ["tests/test_isolation.py::test_closed_run_hunter_finds_nothing", "tests/test_leaks.py::test_seed_salt_blocks_seed_bruteforce",
                                    "tests/test_guards.py::test_agent_cannot_read_parent_environ_salt"], ""),
        ("запись в оценщик", [f"{B}::test_writer_attack_changes_nothing", f"{B}::test_grader_digest_detects_tampered_truth"], "`verify-log`"),
        ("реальные финансовые данные", ["tests/test_round4_pii.py::test_generated_episodes_contain_no_real_data",
                                        "tests/test_round4_pii.py::test_scanner_finds_planted_data"], "`make pii-scan`, `docs/SAFETY.md`"),
        ("неработающее ядро", ["tests/test_config_fuzz.py::test_config_space_fuzz", "tests/test_fuzz.py::test_fuzz_actions"], "`make check`"),
        ("диагностика P, R, F1, возврат, шаги, время", ["tests/test_runner.py::test_eval_mode_child_never_sees_reward"], "`reports/selfcheck.md`"),
    ]),
]


def render() -> str:
    out = ["# Матрица: разделы 05, 10 и блокеры кейса → тесты", "",
           "Сгенерировано `python tools/section10_matrix.py`; тест `tests/test_round4_section10.py` проверяет, что каждый",
           "названный тест существует, и у каждой строки есть хотя бы один тест. Повторить строку: `python -m pytest -q <тест>`.", ""]
    for block, rows in MATRIX:
        out += [f"## {block}", "", "| Что проверяется | Тесты | Где ещё |", "|---|---|---|"]
        for what, tests, extra in rows:
            out.append(f"| {what} | " + "<br>".join(f"`{t}`" for t in tests) + f" | {extra} |")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    (ROOT / "docs" / "SECTION10_MATRIX.md").write_text(render(), "utf-8")
    print("section10-matrix: wrote docs/SECTION10_MATRIX.md")
