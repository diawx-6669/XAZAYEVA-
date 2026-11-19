import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TZ", "UTC")

from auditenv.generator.episode import generate_episode  # noqa: E402


@pytest.fixture(scope="session")
def episodes():
    cache = {}

    def get(seed, cfg="dev-mixed"):
        k = (seed, cfg)
        if k not in cache:
            cache[k] = generate_episode(seed, cfg)
        return cache[k]

    return get


@pytest.fixture(scope="session")
def erroneous(episodes):
    for s in range(1, 50):
        ep = episodes(s, "interaction-heavy")
        if len(ep.truth["issues"]) >= 3:
            return ep
    raise AssertionError("no erroneous episode")


@pytest.fixture(scope="session")
def clean(episodes):
    return episodes(1, "clean-only")
