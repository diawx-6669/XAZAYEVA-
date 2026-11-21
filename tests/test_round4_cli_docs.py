"""B6: documentation does not lag behind the code - every .PHONY make target is in `make help`, every CLI
subcommand and every round-4 make target is mentioned in README.md."""

import re

from auditenv.paths import ROOT

MK = (ROOT / "Makefile").read_text("utf-8")
README = (ROOT / "README.md").read_text("utf-8")


def _phony():
    return re.search(r"^\.PHONY: (.*)$", MK, re.M).group(1).split()


def test_every_phony_target_has_a_help_line():
    help_ = re.search(r"^help:\n((?:\t.*\n)+)", MK, re.M).group(1)
    missing = [t for t in _phony() if t != "help" and not re.search(rf"make {re.escape(t)}\b", help_)]
    assert not missing, missing


def test_every_phony_target_has_a_recipe():
    for t in _phony():
        assert re.search(rf"^{re.escape(t)}:", MK, re.M), t


def test_every_cli_subcommand_is_documented_in_readme():
    src = (ROOT / "auditenv" / "cli.py").read_text("utf-8")
    subs = set(re.findall(r'sub\.add_parser\("([a-z-]+)"', src)) | {"replay", "leakscan"}
    missing = [s for s in sorted(subs) if not re.search(rf"auditenv {re.escape(s)}\b|`{re.escape(s)}`", README)]
    assert not missing, missing


def test_round4_make_targets_in_readme():
    for t in ("repro-cert", "prepublish", "pii-scan", "min-budget", "power", "difficulty", "coverage-map",
              "exhaustive", "bench"):
        assert f"make {t}" in README, t
