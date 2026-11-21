"""B18: verify-release accepts only report/doc-fact changes after the self-check commit."""

import importlib.util

from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("verify_release", ROOT / "tools" / "verify_release.py")
vr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vr)


def test_only_report_changes():
    assert vr.only_report_changes(["reports/selfcheck.md", "README.md", "docs/DESIGN.md", ""]) == []
    assert vr.only_report_changes(["reports/x", "auditenv/env/env.py", "tests/t.py"]) == ["auditenv/env/env.py", "tests/t.py"]
