"""B11: docs/FINDINGS_EXAMPLES.md is up to date; every example validates against the findings schema and is
a TP on its open episode."""

import importlib.util
import json
import re

from auditenv.grader.core import EpisodeGrader
from auditenv.jsonschema_lite import validate
from auditenv.paths import ROOT

_spec = importlib.util.spec_from_file_location("findings_examples", ROOT / "tools" / "findings_examples.py")
fe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fe)


def test_examples_up_to_date_valid_and_true_positive():
    text = (ROOT / "docs" / "FINDINGS_EXAMPLES.md").read_text("utf-8")
    assert text == fe.render(), "run: python tools/findings_examples.py"
    schema = json.loads((ROOT / "schemas" / "findings.schema.json").read_text("utf-8"))
    blocks = re.findall(r"Эпизод `(episodes/\w+/[\w-]+)`.*?```json\n(.*?)```", text, re.S)
    assert len(blocks) == 4
    for path, body in blocks:
        f = json.loads(body)
        ep = ROOT / path
        eid = ep.name
        sub = {"episode_id": eid, "findings": [f]}
        validate(sub, schema)
        r = EpisodeGrader.from_dir(ep / "grader").grade(sub, inspection_steps=0)
        assert r["tp"] == 1 and r["fp"] == 0, (path, r["findings"])
