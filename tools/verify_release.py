"""B18: `make verify-release` - is this commit ready to be tagged and submitted? Read-only.

1. working tree clean;
2. tag v1.2-submission: absent (fine before tagging) or pointing at HEAD;
3. reports/selfcheck.json was produced by `make check` on this code: between its header commit and HEAD only
   files under reports/ changed (and docs facts that docs-check --fix rewrites);
4. reproducibility certificate, SBOM and docs facts are current (repro-cert --check, verify-sbom, docs-check);
5. prepublish report has 0 findings.
Exit code 1 if any check fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "v1.2-submission"
ALLOWED_AFTER_CHECK = ("reports/", "README", "docs/")  # make check output + docs-check --fix of fact numbers


def sh(*args, check=False):
    p = subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def only_report_changes(files: list) -> list:
    return [f for f in files if f and not f.startswith(ALLOWED_AFTER_CHECK)]


def main() -> int:
    py = sys.executable
    results = []
    rc, out = sh("git", "status", "--porcelain")
    results.append(("рабочее дерево чистое", rc == 0 and out == "", out[:200]))
    head = sh("git", "rev-parse", "HEAD")[1]
    rc, tag = sh("git", "rev-parse", f"{TAG}^{{commit}}")
    results.append((f"тег {TAG}", rc != 0 or tag == head, "ещё не поставлен" if rc else ("= HEAD" if tag == head else f"указывает на {tag[:12]}, не на HEAD")))
    sc = json.loads((ROOT / "reports" / "selfcheck.json").read_text("utf-8"))
    c = sc["header"]["commit"]
    rc, files = sh("git", "diff", "--name-only", c, "HEAD")
    bad = only_report_changes(files.splitlines()) if rc == 0 else ["unknown commit " + c]
    results.append(("selfcheck снят с этого кода", not bad, f"заголовок {c}; после него менялись: {bad[:5]}" if bad else f"заголовок {c}"))
    for name, cmd in (("сертификат воспроизводимости", [py, "tools/repro_cert.py", "--check"]),
                      ("SBOM", [py, "-m", "auditenv", "verify-sbom"]),
                      ("docs-check", [py, "-m", "auditenv", "docs-check"]),
                      ("prepublish", [py, "tools/prepublish.py"])):
        rc, out = sh(*cmd)
        results.append((name, rc == 0, out.splitlines()[-1] if out else ""))
    for name, ok, note in results:
        print(f"{'OK  ' if ok else 'FAIL'} {name}: {note}")
    bad = sum(1 for _, ok, _ in results if not ok)
    print(f"verify-release: {len(results) - bad}/{len(results)} OK" + ("" if not bad else " - NOT ready to tag"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
