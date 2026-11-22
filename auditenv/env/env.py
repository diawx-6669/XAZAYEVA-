"""AuditEnv: Gymnasium-style JSON contract.

    env = AuditEnv(mode="train" | "eval", grader_log=None)
    obs, info = env.reset(seed=..., config=...)        # or reset(episode_dir=...)
    obs, reward, terminated, truncated, info = env.step({"tool": ..., "args": {...}})

Observations contain only {result | error, steps_remaining} (first one: task, manifest,
policy_summary, steps_remaining). Intermediate reward is always 0. In "train" mode the
terminal reward and metrics are returned; in "eval" mode reward=0 and info={} and the
outcome goes only to the grader log.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..grader.core import EpisodeGrader
from ..grader.log import GraderLog
from .cursors import CursorCodec
from .data import PublicData
from .errors import BAD_ARGS, EPISODE_OVER, UNKNOWN_TOOL, ToolError
from .tools import DISPATCH, PAGE_MAX, TOOLS, check_args

MAX_STEPS = 100
_MALFORMED = {"__malformed_submit__": True}
TIME_LIMIT_S = 60.0

DEFAULT_SEED = 0


def task_text(tolerance_minor: int = 1) -> str:
    unit = "minor unit" if tolerance_minor == 1 else "minor units"
    return (
        "You are auditing one fictional company for one reporting period. Find financial errors in the "
        "books and submit findings with evidence. Error types: duplicate_invoice (affected_ids=[invoice_id of "
        "the later copy]), payment_allocation (affected_ids=[payment_id]), fx_rate (affected_ids=[invoice_id or "
        "payment_id of the mis-converted document]), period_cutoff (affected_ids=[invoice_id]), vat_error "
        "(affected_ids=[invoice_id]; a 'VAT 12%' line must equal 12% of the other lines, half-even). "
        f"claimed_amount_minor = absolute distortion in base currency minor units (tolerance: {tolerance_minor} "
        f"{unit}); currency = base currency. For payment_allocation the amount is the part of the receipt "
        "left on Unapplied Cash (2400) instead of Accounts Receivable (1200), converted at the payment's policy "
        "rate (for a foreign-currency receipt this does not depend on the rate posted to Cash). "
        "evidence_ids may contain doc_id, ledger row_id, fx id (fx:DATE:SRC:TGT) and "
        "'policy'. Clean books exist: submitting nothing can be correct. Tools: list_records(table, cursor, "
        f"limit<={PAGE_MAX}), get_record(table, id), get_document(doc_id), calculator(expression), "
        "submit(findings={episode_id, findings:[{type, affected_ids, claimed_amount_minor, currency, "
        "evidence_ids, explanation}]}) - the flat form submit(episode_id, findings:[...]) is accepted too; a "
        f"malformed submission ends the episode with reward -1. Budget: {MAX_STEPS} steps including submit; "
        "every action, even an error, uses a step. Reward = clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)."
    )


TASK = task_text(1)


def submission_from_args(args):
    """Both submit forms map to one findings object; anything else is a malformed submission (None).

    nested: {"findings": {"episode_id": ..., "findings": [...]}}
    flat:   {"episode_id": ..., "findings": [...]}
    """
    if not isinstance(args, dict):
        return None
    if set(args) == {"findings"} and isinstance(args["findings"], dict):
        return args["findings"]
    if set(args) == {"episode_id", "findings"} and isinstance(args["findings"], list):
        return {"episode_id": args["episode_id"], "findings": args["findings"]}
    return None


def policy_summary(policy: dict) -> dict:
    keys = ("fx_rate_date", "fx_rate_date_basis", "fx_missing_rate", "fx_business_days", "fx_holidays", "fx_rate_meaning",
            "period_boundary",
            "rounding", "recognition", "payment_allocation", "unapplied_cash", "credit_notes", "vat")
    return {k: policy[k] for k in keys}


def _schema(name):
    import json

    from ..paths import SCHEMAS_DIR

    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text("utf-8"))


def _check_seed(seed):
    if seed is None:
        return DEFAULT_SEED
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError(f"seed must be an int (got {type(seed).__name__}); bool and float are rejected")
    return seed


class AuditEnv:
    """Gymnasium-compatible without inheriting gymnasium.Env (the case allows that): reset/step,
    close, render (no-op), metadata, context manager, action_space/observation_space as JSON
    Schemas (dicts) from schemas/."""

    metadata = {"render_modes": [], "render_fps": None, "contract": "auditenv-json-1"}
    render_mode = None
    reward_range = (-1.0, 1.0)

    def __init__(self, mode: str = "train", grader_log=None, time_limit: float = TIME_LIMIT_S, clock=None,
                 max_steps: int = MAX_STEPS, config=None):
        if mode not in ("train", "eval"):
            raise ValueError("mode must be 'train' or 'eval'")
        self.mode = mode
        self.config = config
        self.action_space = _schema("action")
        self.observation_space = _schema("observation")
        self.log = grader_log if isinstance(grader_log, GraderLog) else GraderLog(grader_log)
        self.time_limit = time_limit
        self.clock = clock or time.monotonic
        self.max_steps = max_steps
        self.run_meta: dict = {}
        self._data = None
        self._done = True
        self._steps = 0
        self._terminated = True
        self._truncated = False
        self.last_grade = None

    # ----------------------------------------------------------------- reset
    def reset(self, seed=None, config=None, *, episode_dir=None, episode=None, options=None):
        if self._data is not None and not self._done:
            # The previous episode was abandoned (reset before submit/limit): the grader log records it,
            # so a training loop cannot silently drop bad episodes from its statistics.
            self.log.write({"episode_id": self._data.episode_id, "abandoned": True, "inspection_steps": self._steps,
                            "mode": self.mode, **self.run_meta})
            self._done = True
        if options:
            episode_dir = options.get("episode_dir", episode_dir)
            config = options.get("config", config)
        if episode_dir is not None:
            d = Path(episode_dir)
            data = PublicData.from_dir(d / "public")
            grader = EpisodeGrader.from_dir(d / "grader")
        else:
            if episode is None:
                from ..generator.episode import generate_episode

                episode = generate_episode(_check_seed(seed), config if config is not None else self.config)
            data = PublicData(episode.files)
            grader = EpisodeGrader(episode.truth)
        self._data = data
        self._grader = grader
        self._codec = CursorCodec(data.episode_id, data.digest)
        self._steps = 0
        self._done = False
        self._terminated = False
        self._truncated = False
        self._seen: set = set()
        self._t0 = self.clock()
        self.last_grade = None
        self.truncation_reason = None
        obs = {
            "task": task_text(grader.tolerance),
            "manifest": dict(data.manifest),
            "policy_summary": policy_summary(data.policy),
            "steps_remaining": self.max_steps,
        }
        info = {} if self.mode == "eval" else {"mode": "train"}
        return obs, info

    @property
    def episode_id(self):
        return self._data.episode_id if self._data else None

    @property
    def steps_used(self) -> int:
        return self._steps

    def _remaining(self) -> int:
        return self.max_steps - self._steps

    # ------------------------------------------------------------------ step
    def step(self, action):
        if self._data is None or self._done:
            remaining = max(0, self._remaining()) if self._data else 0
            return {"error": {"code": EPISODE_OVER}, "steps_remaining": remaining}, 0.0, self._terminated, \
                self._truncated, {}
        if self.clock() - self._t0 > self.time_limit:
            return self._finish(None, truncated=True, obs_body={"error": {"code": EPISODE_OVER}}, count=False,
                                reason="time_limit")
        self._steps += 1
        tool, args, err = None, None, None
        if not isinstance(action, dict) or set(action) - {"tool", "args"} or not isinstance(action.get("tool"), str):
            err = BAD_ARGS
            if isinstance(action, dict) and action.get("tool") == "submit":
                tool = "submit"
        else:
            tool = action["tool"]
            args = action.get("args")
            if args is None and tool != "submit":
                args = {}
            if tool not in TOOLS:
                err = UNKNOWN_TOOL
            else:
                try:
                    check_args(tool, args)
                except ToolError as e:
                    err = e.code
        if tool == "submit" and err in (None, BAD_ARGS):
            # Any submit ends the episode. A malformed one (no/empty args, wrong shape) is graded as an
            # invalid findings object: reward -1, reason in the grader log, no details to the agent.
            sub = submission_from_args(args)
            return self._finish(sub if sub is not None else _MALFORMED, truncated=False,
                                obs_body={"result": {"submitted": True}})
        if err is None:
            try:
                result, seen = DISPATCH[tool](self._data, self._codec, args)
                self._seen.update(seen)
                body = {"result": result}
            except ToolError as e:
                body = {"error": {"code": e.code}}
        else:
            body = {"error": {"code": err}}
        if self._remaining() <= 0:
            return self._finish(None, truncated=True, obs_body=body, reason="max_steps")
        return {**body, "steps_remaining": self._remaining()}, 0.0, False, False, {}

    # ------------------------------------------------------- gymnasium extras
    def render(self):
        """No-op: the environment is text/JSON only (metadata['render_modes'] is empty)."""
        return None

    def close(self):
        self._data = None
        self._done = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    @property
    def spec(self):
        from ..contract import CONTRACT

        return CONTRACT

    def truncate_now(self):
        """Used by the runner when the policy process hangs or dies."""
        if self._done:
            return None
        return self._finish(None, truncated=True, obs_body={"error": {"code": EPISODE_OVER}}, count=False,
                            reason="policy_unresponsive")

    def _finish(self, findings, truncated: bool, obs_body: dict, count: bool = True, reason=None):
        self.truncation_reason = reason if truncated else None
        # truncation (step limit, timeout or a hung policy) is charged the full budget, so hanging
        # never beats an honest submit (jury sim finding #5)
        inspection = self.max_steps if truncated else self._steps - 1
        g = self._grader.grade(findings, inspection_steps=inspection, seen_ids=frozenset(self._seen),
                               truncated=truncated)
        g = {**g, "mode": self.mode, "truncation_reason": self.truncation_reason, **self.run_meta}
        self.last_grade = g
        self.log.write(g)
        self._done = True
        self._terminated = not truncated
        self._truncated = truncated
        obs = {**obs_body, "steps_remaining": self._remaining()}
        if self.mode == "eval":
            return obs, 0.0, self._terminated, self._truncated, {}
        info = {k: g[k] for k in ("valid", "tp", "fp", "fn", "precision", "recall", "f1", "reward_experimental")}
        return obs, g["reward"], self._terminated, self._truncated, info
