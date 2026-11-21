"""Gymnasium wrapper for AuditEnv (optional: `pip install gymnasium` is NOT a project dependency).

Observations and actions are JSON strings (spaces.Text), because the env's observations are nested
records and its actions are tool calls. Reward, terminated, truncated and info are passed through.

    import gymnasium as gym
    from examples.gym_wrapper import AuditGymEnv
    env = AuditGymEnv(config="dev-mixed", mode="train")
    obs, info = env.reset(seed=7)
    obs, reward, terminated, truncated, info = env.step('{"tool": "submit", "args": {"findings": []}}')

The episode and the answer key live in the same process here: fine for training loops, not for an
honest evaluation (use `python -m auditenv run --policy-cmd ...`, docs/ADAPTER.md).
"""

from __future__ import annotations

import json

import gymnasium as gym
from gymnasium import spaces

from auditenv.canon import dumps
from auditenv.env.env import AuditEnv

MAX_OBS_CHARS = 2_000_000
MAX_ACTION_CHARS = 200_000
_CHARSET = frozenset(chr(i) for i in range(32, 127)) | frozenset("\n\t")


class AuditGymEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config="dev-mixed", mode: str = "train", episode_dir=None):
        super().__init__()
        self._config, self._episode_dir = config, episode_dir
        self._env = AuditEnv(mode=mode)
        # JSON is ASCII-safe with ensure_ascii; the charset keeps spaces.Text.contains() meaningful
        self.observation_space = spaces.Text(max_length=MAX_OBS_CHARS, charset=_CHARSET)
        self.action_space = spaces.Text(max_length=MAX_ACTION_CHARS, charset=_CHARSET)

    @staticmethod
    def _enc(obs) -> str:
        return json.dumps(json.loads(dumps(obs)), ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if self._episode_dir is not None:
            obs, info = self._env.reset(episode_dir=self._episode_dir)
        else:
            obs, info = self._env.reset(seed=0 if seed is None else seed, config=self._config)
        return self._enc(obs), dict(info)

    def step(self, action):
        if isinstance(action, str):
            try:
                action = json.loads(action)
            except json.JSONDecodeError:
                action = {"tool": "__invalid__"}  # same as the JSON-lines adapter: unknown_tool, step spent
        obs, reward, terminated, truncated, info = self._env.step(action)
        return self._enc(obs), float(reward), bool(terminated), bool(truncated), dict(info)

    def close(self):
        self._env.close()
