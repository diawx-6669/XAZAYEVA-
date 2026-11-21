"""B2: `python -m auditenv grade <episode_dir> <findings.json> [--steps N]` - grade a findings file offline.

GRADER-SIDE TOOL (reads grader/truth.json, checked against index.json digests). Lets a jury member type an
answer by hand and see exactly how the matcher treats every finding: matched issue or the reason code
(wrong_type, ids_mismatch, amount_out_of_tolerance, currency_mismatch, evidence_incomplete,
duplicate_finding, unmatched), then TP/FP/FN, P/R/F1 and the reward for N inspection steps.
The file may hold {"episode_id", "findings": [...]} or just the list of findings.
"""

from __future__ import annotations

import json
from pathlib import Path

from .grader.core import EpisodeGrader


def grade_file(episode_dir, findings_path, steps: int = 0) -> dict:
    g = EpisodeGrader.from_dir(Path(episode_dir) / "grader")
    raw = json.loads(Path(findings_path).read_text("utf-8"))
    sub = {"episode_id": g.episode_id, "findings": raw} if isinstance(raw, list) else raw
    return g.grade(sub, inspection_steps=steps)


def main(episode_dir, findings_path, steps: int = 0, as_json: bool = False) -> int:
    r = grade_file(episode_dir, findings_path, steps)
    if as_json:
        print(json.dumps(r, ensure_ascii=False, sort_keys=True))
        return 0
    if not r["valid"]:
        print(f"grade: INVALID submission ({r['error']}) -> reward -1.0")
        return 0
    print(f"grade: {r['episode_id']}  truth={r['n_truth']}  findings={r['n_findings']}  steps={steps}")
    for f in r["findings"]:
        print(f"  #{f['index']}: " + (f"TP -> {f['matched']}" if f["matched"] else f"FP ({f['reason']})"))
    for iid in r.get("missed", []):
        print(f"  missed: {iid}")
    print(f"TP={r['tp']} FP={r['fp']} FN={r['fn']}  P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f}  "
          f"reward={r['reward']:+.3f}")
    return 0
