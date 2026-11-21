"""Jury policy: oracle "for the grader only". Reads truth.json of a CLOSED episode written to
disk by the jury (path given in argv) and submits every issue with its first evidence set.
It must never be used as an agent: it proves the maximum reward, not agent skill.
Optional argv[2]: id_map.json to translate truth of the ORIGINAL episode into new IDs."""
import json
import sys

from jl import Conn, run


def main(c: Conn):
    truth = json.load(open(sys.argv[1], encoding="utf-8"))
    idmap = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else None
    first = c.start()
    ep = first["manifest"]["episode_id"]
    tr = (lambda x: idmap.get(x, x)) if idmap else (lambda x: x)
    findings = [{"type": i["type"], "affected_ids": [tr(a) for a in i["affected_ids"]],
                 "claimed_amount_minor": i["expected_amount_minor"], "currency": i["currency"],
                 "evidence_ids": [tr(e) for e in i["evidence_sets"][0]], "explanation": "oracle"}
                for i in truth["issues"]]
    c.submit(ep, findings)


run(main)
