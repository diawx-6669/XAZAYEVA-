"""D3: every config is versioned and locked: content change without a version bump fails."""

import json
from pathlib import Path

import auditenv.config as C

ROOT = Path(__file__).resolve().parent.parent
LOCK = json.loads((ROOT / "configs" / "LOCK.json").read_text())


def test_lock_is_current():
    assert C.check_lock(LOCK) == []


def test_content_change_without_version_bump_fails(monkeypatch):
    monkeypatch.setitem(C.DEFAULT_CONFIG, "foreign_share", 0.31)  # a moved generator default changes every config
    problems = C.check_lock(LOCK)
    assert problems and all("bump 'version'" in p for p in problems)


def test_version_bump_alone_asks_for_lock_refresh():
    stale = [dict(e, version="0.9") for e in LOCK]
    assert all("stale" in p for p in C.check_lock(stale))


def test_changelog_mentions_every_locked_version():
    log = (ROOT / "configs" / "CHANGELOG.md").read_text()
    assert all(f"| {e['version']} |" in log for e in LOCK)


def test_manifest_carries_version_and_hash():
    from auditenv.generator.episode import generate_episode

    m = generate_episode(1, "dev-mixed").public().manifest
    entry = [e for e in LOCK if e["name"] == "dev-mixed"][0]
    assert m["config_version"] == entry["version"] and m["config_hash"] == entry["config_hash"]
