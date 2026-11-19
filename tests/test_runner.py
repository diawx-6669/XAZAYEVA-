"""Process isolation and the runner protocol."""

import os

from auditenv.runner import ChildPolicy, run_episode


def test_policy_runs_in_another_process(erroneous):
    c = ChildPolicy("simple_reconcile")
    try:
        assert c.proc.pid != os.getpid()
        assert os.path.realpath(c.tmp.name) != os.path.realpath(os.getcwd())
    finally:
        c.close()


def test_eval_mode_child_never_sees_reward(erroneous, tmp_path):
    r = run_episode("simple_reconcile", episode=erroneous, mode="eval", grader_log=tmp_path / "log.jsonl")
    assert r["returned_reward"] == 0.0
    assert all(x["reward"] == 0.0 for x in r["trajectory"])
    assert (tmp_path / "log.jsonl").read_text().count("\n") == 1


def test_dead_policy_truncates(erroneous, monkeypatch):
    class Dead:
        def act(self, *a, **k):
            return None

        def close(self):
            pass

    import auditenv.runner as rn

    monkeypatch.setattr(rn, "ChildPolicy", lambda *a, **k: Dead())
    r = rn.run_episode("simple_reconcile", episode=erroneous)
    assert r["grade"]["truncated"] and r["grade"]["n_findings"] == 0


def test_baselines_fit_in_budget_and_time(erroneous):
    for pol in ("random_explorer", "simple_reconcile", "flag_all", "oracle"):
        g = run_episode(pol, episode=erroneous)["grade"]
        assert g["steps"] <= 100 and g["elapsed_s"] < 60
