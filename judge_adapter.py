"""Jury adapter (Genesis FinTech "Определения проверок", 20.11.2026) over AuditEnv.

    generate_episode(seed, config, output_dir) -> None   public/ + private/ (truth.json, provenance.json)
    make_env()                                           object with reset(seed, config) / step(action)
    score_episode(episode_dir, findings, inspection_steps) -> {"tp","fp","fn","precision","recall","f1","return"}

The adapter only translates envelopes and names; it never chooses actions. Working directory: repository
root (in the image /app). Type names are the case's four types plus vat_error: duplicate_invoice,
payment_allocation, fx_rate (= FX conversion), period_cutoff, vat_error.

Closed mode never reads private/: the env is given the public files and an EMPTY answer key, and the reward
returned to the policy is 0; the true score is computed only by score_episode on the jury side.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auditenv.env.env import AuditEnv  # noqa: E402
from auditenv.generator.episode import generate_episode as _generate  # noqa: E402
from auditenv.generator.export import dumps_bytes  # noqa: E402
from auditenv.grader.core import EpisodeGrader  # noqa: E402

PUBLIC = ("manifest.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv", "policy.json")
ERROR_CODES = {"not_found": "UNKNOWN_ID", "unknown_tool": "UNKNOWN_ACTION", "bad_args": "MALFORMED_ACTION",
               "invalid_cursor": "INVALID_CURSOR", "calc_error": "CALC_ERROR", "episode_over": "EPISODE_ENDED"}
MESSAGES = {"UNKNOWN_ID": "no such record", "UNKNOWN_ACTION": "unknown action", "MALFORMED_ACTION": "bad arguments",
            "INVALID_CURSOR": "invalid cursor", "CALC_ERROR": "expression not allowed",
            "EPISODE_ENDED": "episode is over", "RESET_REQUIRED": "call reset first"}


def _cfg(config):
    """team_config may be {} / None (defaults), a config name ("dev-mixed") or a config dict."""
    if not config:
        return None
    if isinstance(config, dict) and "name" in config and len(config) == 1:
        return config["name"]
    return config


def generate_episode(seed: int, config: dict, output_dir: str) -> None:
    ep = _generate(int(seed), _cfg(config))
    out = Path(output_dir)
    (out / "public").mkdir(parents=True, exist_ok=True)
    (out / "private").mkdir(parents=True, exist_ok=True)
    for name, data in ep.files.items():
        (out / "public" / name).write_bytes(data)
    (out / "private" / "truth.json").write_bytes(dumps_bytes(ep.truth))
    (out / "private" / "provenance.json").write_bytes(dumps_bytes(ep.provenance))


class _PublicEpisode:
    """Public files + an empty answer key: what the env needs in closed mode, and nothing else."""

    def __init__(self, files: dict):
        self.files = files
        man = json.loads(files["manifest.json"])
        self.episode_id = man["episode_id"]
        self.truth = {"episode_id": self.episode_id, "issues": []}


def _public_files(episode_dir: str) -> dict:
    d = Path(episode_dir)
    pub = d / "public" if (d / "public").is_dir() else d
    return {name: (pub / name).read_bytes() for name in PUBLIC}


class JudgeEnv:
    def __init__(self):
        self._env = None
        self._mode = None
        self._episode_id = None

    def reset(self, seed=0, config=None):
        config = dict(config or {})
        mode = config.get("mode", "train")
        if mode not in ("closed", "train"):
            raise ValueError("config.mode must be 'closed' or 'train'")
        if mode == "closed":
            if not config.get("episode_dir"):
                raise ValueError("closed mode needs config.episode_dir")
            env = AuditEnv(mode="eval")
            obs, _ = env.reset(episode=_PublicEpisode(_public_files(config["episode_dir"])))
        else:
            env = AuditEnv(mode="train")
            if config.get("episode_dir"):
                obs, _ = env.reset(episode_dir=config["episode_dir"]) if (Path(config["episode_dir"]) / "grader").is_dir() \
                    else env.reset(episode=_train_episode(config["episode_dir"]))
            else:
                obs, _ = env.reset(seed=int(seed), config=_cfg(config.get("team_config")))
        self._env, self._mode = env, mode
        self._episode_id = obs["manifest"]["episode_id"]
        policy = env._data.policy if hasattr(env, "_data") else obs.get("policy_summary")
        first = {"task": obs["task"], "manifest": obs["manifest"], "policy": copy.deepcopy(policy),
                 "remaining_steps": obs["steps_remaining"]}
        info = {"mode": mode, "tools": ["list_records", "get_record", "get_document", "calculator", "submit"],
                "tables": ["ledger", "invoices", "payments", "fx"],
                "error_types": ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff", "vat_error"]}
        return first, info

    def step(self, action):
        if self._env is None:
            return ({"result": None, "error": {"code": "RESET_REQUIRED", "message": MESSAGES["RESET_REQUIRED"]},
                     "remaining_steps": 0}, 0.0, False, False, {})
        if not isinstance(action, dict) or not isinstance(action.get("name"), str) \
                or not isinstance(action.get("args", {}), dict):
            inner = {"tool": "__malformed__", "args": {}}
        else:
            args = dict(action.get("args") or {})
            if action["name"] == "submit" and isinstance(args.get("findings"), dict) \
                    and "episode_id" not in args["findings"]:
                args["findings"] = {"episode_id": self._episode_id, **args["findings"]}
            inner = {"tool": action["name"], "args": args}
        obs, reward, terminated, truncated, info = self._env.step(inner)
        if "error" in obs:
            code = ERROR_CODES.get(obs["error"].get("code"), "MALFORMED_ACTION")
            out = {"result": None, "error": {"code": code, "message": MESSAGES.get(code, "error")}}
        else:
            res = obs.get("result")
            name = action.get("name") if isinstance(action, dict) else None
            if name == "submit":
                res = {"accepted": True}
            elif name == "calculator" and isinstance(res, dict) and "value" in res:
                res = res["value"]                                    # a decimal string, e.g. "0.3"
            elif name == "get_record" and isinstance(res, dict) and "record" in res:
                res = res["record"]                                   # the record object itself
            elif name == "get_document" and isinstance(res, dict) and "document" in res:
                res = dict(res["document"], document_type=res.get("kind"))  # the document object itself
            out = {"result": res, "error": None}
        out["remaining_steps"] = obs.get("steps_remaining", 0)
        if self._mode == "closed":
            reward, info = 0.0, {}
        return out, float(reward), bool(terminated), bool(truncated), info


def _train_episode(episode_dir):
    d = Path(episode_dir)
    ep = _PublicEpisode(_public_files(episode_dir))
    for p in (d / "private" / "truth.json", d / "truth.json"):
        if p.exists():
            ep.truth = json.loads(p.read_text("utf-8"))
            break
    return ep


def make_env():
    return JudgeEnv()


def score_episode(episode_dir: str, findings: dict, inspection_steps: int) -> dict:
    d = Path(episode_dir)
    truth_path = next(p for p in (d / "private" / "truth.json", d / "grader" / "truth.json", d / "truth.json")
                      if p.exists())
    grader = EpisodeGrader(json.loads(truth_path.read_text("utf-8")))
    sub = findings
    if isinstance(sub, dict) and "episode_id" not in sub:
        sub = {"episode_id": grader.episode_id, **sub}
    g = grader.grade(sub, inspection_steps=int(inspection_steps))
    if not g["valid"]:
        return {"tp": None, "fp": None, "fn": None, "precision": None, "recall": None, "f1": None, "return": -1.0}
    return {"tp": g["tp"], "fp": g["fp"], "fn": g["fn"], "precision": g["precision"], "recall": g["recall"],
            "f1": g["f1"], "return": g["reward"]}
