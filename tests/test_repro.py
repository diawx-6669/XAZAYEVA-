"""Reproducibility and generalization: byte-identical regeneration, deterministic replay,
transforms preserve oracle reward/F1, golden hashes."""

import hashlib
import json
from pathlib import Path

import pytest

from auditenv.canon import dumps, files_digest
from auditenv.generator.episode import generate_episode
from auditenv.generator.transforms import transform_episode
from auditenv.grader.validate_truth import validate
from auditenv.runner import run_episode

GOLDEN = json.loads((Path(__file__).parent / "golden_hashes.json").read_text())


@pytest.mark.parametrize("seed,cfg", [(1, "dev-mixed"), (2, "interaction-heavy"), (3, "clean-only"), (4, "train-easy")])
def test_same_seed_same_bytes(seed, cfg):
    a, b = generate_episode(seed, cfg), generate_episode(seed, cfg)
    assert a.files == b.files and dumps(a.truth) == dumps(b.truth) and dumps(a.provenance) == dumps(b.provenance)


def test_different_seeds_differ():
    assert generate_episode(1, "dev-mixed").files != generate_episode(2, "dev-mixed").files


def test_config_change_changes_hash():
    a = generate_episode(1, "dev-mixed").public().manifest["config_hash"]
    b = generate_episode(1, "interaction-heavy").public().manifest["config_hash"]
    assert a != b


@pytest.mark.parametrize("policy", ["random_explorer", "simple_reconcile", "flag_all"])
def test_same_actions_same_trajectory_and_rewards(erroneous, policy):
    t1 = run_episode(policy, episode=erroneous, isolate=True)["trajectory"]
    t2 = run_episode(policy, episode=erroneous, isolate=False)["trajectory"]
    assert [dumps(x) for x in t1] == [dumps(x) for x in t2]


@pytest.mark.parametrize("seed,cfg", [(s, c) for s in range(4) for c in ("dev-mixed", "interaction-heavy")])
def test_transform_preserves_oracle_and_f1(seed, cfg):
    ep = generate_episode(seed, cfg)
    twin, mapping = transform_episode(ep, 100 + seed)
    assert twin.files != ep.files and twin.episode_id != ep.episode_id
    pd, tpd = ep.public(), twin.public()
    assert sorted(r["row_id"] for r in tpd.ledger) != sorted(r["row_id"] for r in pd.ledger)
    assert validate(tpd, twin.truth)["ok"]
    for pol in ("oracle", "simple_reconcile"):
        g1 = run_episode(pol, episode=ep, isolate=False)["grade"]
        g2 = run_episode(pol, episode=twin, isolate=False)["grade"]
        assert (g1["reward"], g1["f1"], g1["tp"]) == (g2["reward"], g2["f1"], g2["tp"])
    # mapped truth: same structure with renamed IDs
    for a, b in zip(ep.truth["issues"], twin.truth["issues"]):
        assert [mapping[x] for x in a["affected_ids"]] == b["affected_ids"] or sorted(
            mapping[x] for x in a["affected_ids"]) == b["affected_ids"]
        assert a["expected_amount_minor"] == b["expected_amount_minor"]


@pytest.mark.parametrize("key", sorted(GOLDEN))
def test_golden_hashes(key):
    cfg, seed = key.split("#")
    ep = generate_episode(int(seed), cfg)
    assert files_digest(ep.files) == GOLDEN[key]["public"]
    assert hashlib.sha256(dumps(ep.truth).encode()).hexdigest() == GOLDEN[key]["truth"]


def test_exported_episodes_match_generator():
    root = Path(__file__).parent.parent / "episodes"
    from auditenv.generator.export import read_public_files

    for split in ("train", "dev"):
        idx = json.loads((root / split / "index.json").read_text())
        assert len(idx) == 10
        for e in idx[:3]:
            ep = generate_episode(e["seed"], e["config"])
            assert files_digest(read_public_files(root / split / e["episode_id"] / "public")) == files_digest(ep.files)
