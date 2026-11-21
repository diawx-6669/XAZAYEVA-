"""A8: the prepublish scanner recognises secrets, ignores placeholders and finds no gaps in .gitignore.

Fake secrets are assembled at run time so that this file itself never matches the history scan."""

import importlib.util
import re

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("prepublish", ROOT / "tools" / "prepublish.py")
pp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pp)


def _hits(line):
    return [name for name, pat in pp.SECRET_PATTERNS if re.search(pat, line)]


def test_secret_patterns_fire_on_fakes():
    fakes = {
        "github_token": "token " + "gh" + "p_" + "A1b2" * 9,
        "aws_access_key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "private_key": "-----BEGIN " + "RSA PRIVATE KEY-----",
        "anthropic_key": "sk-" + "ant-" + "x" * 30,
        "seed_salt_value": "export AUDITENV_SEED_SALT" + "=" + "q8Zr2LmX9a",
    }
    for name, line in fakes.items():
        assert name in _hits(line), (name, line)


def test_placeholders_are_not_secrets():
    for line in ["-e AUDITENV_SEED_SALT=<секрет> auditenv", "export AUDITENV_SEED_SALT='<ваш секрет>'",
                 "AUDITENV_SEED_SALT=$SALT", "AUDITENV_SEED_SALT= python", "if AUDITENV_SEED_SALT=...",
                 "sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535"]:
        assert _hits(line) == [], line


def test_forbidden_paths():
    assert any(re.search(p, "jury_sim/work/salt.txt") for p in pp.FORBIDDEN_PATHS)
    assert not any(re.search(p, "jury_sim/grader.py") for p in pp.FORBIDDEN_PATHS)


def test_gitignore_has_no_gaps():
    import pytest

    if not (ROOT / ".git").exists() or not (ROOT / ".gitignore").exists():  # inside the image
        pytest.skip("not a git checkout")
    assert pp.gitignore_gaps() == []


def test_allowlist_splits_findings():
    keep, allowed = pp.split_allowed(["a: x", "b: y"], [("b:", "known")])
    assert keep == ["a: x"] and allowed == ["b: y  [allowed: known]"]
