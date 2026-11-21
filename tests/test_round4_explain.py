"""A17: explain recomputes every injected amount from the provenance snapshots; examples are up to date,
offline, and the tool refuses closed (salted) episodes."""

import json
import re

import pytest

from auditenv.cli import episode_dirs
from auditenv.explain import EXAMPLES, recompute, render
from auditenv.generator.episode import generate_episode
from auditenv.paths import ROOT


def test_amounts_recomputed_from_snapshots_on_all_open_episodes():
    n = 0
    for _, d in episode_dirs():
        truth = json.loads((d / "grader" / "truth.json").read_text("utf-8"))
        prov = json.loads((d / "grader" / "provenance.json").read_text("utf-8"))
        muts = {m["issue_id"]: m for m in prov["mutations"]}
        for iss in truth["issues"]:
            assert recompute(iss, muts[iss["issue_id"]])[0] == iss["expected_amount_minor"], (d.name, iss["issue_id"])
            n += 1
    assert n >= 30


def test_amounts_recomputed_on_fresh_interaction_episodes():
    for seed in range(15):
        ep = generate_episode(680000 + seed, "interaction-heavy")
        muts = {m["issue_id"]: m for m in ep.provenance["mutations"]}
        for iss in ep.truth["issues"]:
            assert recompute(iss, muts[iss["issue_id"]])[0] == iss["expected_amount_minor"], (seed, iss)


def test_examples_up_to_date_and_offline():
    for eid in EXAMPLES:
        page = (ROOT / "site" / "explain" / f"{eid}.html").read_text("utf-8")
        assert page == render(ROOT / "episodes" / "dev" / eid)
        assert "НЕ совпадает" not in page and "Инструмент оценщика" in page
        assert not re.search(r"(src|href)=['\"]https?://", page) and "<script" not in page


def test_refuses_salted_episode(tmp_path, monkeypatch):
    from auditenv.generator.export import write_episode

    monkeypatch.setenv("AUDITENV_SEED_SALT", "closed-run")
    ep = generate_episode(5, "dev-mixed")
    monkeypatch.delenv("AUDITENV_SEED_SALT")
    write_episode(ep, tmp_path / "ep")
    with pytest.raises(SystemExit, match="salted"):
        render(tmp_path / "ep")
