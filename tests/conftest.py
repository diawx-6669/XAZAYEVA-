import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TZ", "UTC")

from auditenv.generator.episode import generate_episode  # noqa: E402


def _process_environ_text(pid):
    """The kernel's view of another process's environment as text, or None when the OS does not show it.
    Linux: /proc/<pid>/environ (PermissionError propagates: root without CAP_SYS_PTRACE, another uid).
    macOS has no /proc: `ps -E` prints the environment of a same-uid process after its command line."""
    if Path("/proc/self").exists():
        return Path(f"/proc/{pid}/environ").read_bytes().decode(errors="replace").replace("\0", "\n")
    if sys.platform == "darwin":
        import subprocess

        out = subprocess.run(["ps", "-E", "-ww", "-o", "command=", "-p", str(pid)], capture_output=True, text=True)
        return out.stdout if out.returncode == 0 else None
    return None


@pytest.fixture
def process_environ():
    return _process_environ_text


@pytest.fixture(autouse=True)
def _no_seed_salt(request, monkeypatch):
    """Open tests must see the open (unsalted) generator even if the evaluator's secret salt is set in
    the shell. Tests marked `salt` (isolation tests) manage AUDITENV_SEED_SALT themselves."""
    if request.node.get_closest_marker("salt") is None:
        monkeypatch.delenv("AUDITENV_SEED_SALT", raising=False)


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
