"""B12: reports/episode_cards.md matches the committed open episodes."""

import importlib.util

from auditenv.paths import ROOT
import pytest

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick

_spec = importlib.util.spec_from_file_location("episode_cards", ROOT / "tools" / "episode_cards.py")
ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ec)


def test_episode_cards_up_to_date():
    assert (ROOT / "reports" / "episode_cards.md").read_text("utf-8") == ec.render(), "run: python tools/episode_cards.py"


def test_trajectory_stats_up_to_date():
    spec = importlib.util.spec_from_file_location("trajectory_stats", ROOT / "tools" / "trajectory_stats.py")
    ts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ts)
    assert (ROOT / "reports" / "trajectory_stats.md").read_text("utf-8") == ts.render()
