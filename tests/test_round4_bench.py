"""A18: the env pool is deterministic - 2 workers return exactly what 1 worker returns."""

import sys

from auditenv.paths import ROOT

sys.path.insert(0, str(ROOT))
from examples.env_pool import EnvPool, size_config  # noqa: E402
import pytest

pytestmark = pytest.mark.slow  # heavy round-4 check: in make check, not in make quick


def test_pool_results_do_not_depend_on_worker_count():
    jobs = [(740000 + s, "dev-mixed") for s in range(6)]
    strip = lambda rs: [(r["seed"], r["reward"], r["steps"], r["f1"]) for r in rs]  # noqa: E731
    with EnvPool(workers=1) as p1:
        a = strip(p1.run(jobs))
    with EnvPool(workers=2) as p2:
        b = strip(p2.run(jobs))
    assert a == b and len(a) == 6


def test_size_configs_are_valid():
    from auditenv.config import validate_config

    for t in (200, 1000, 2000):
        validate_config(size_config(t))
