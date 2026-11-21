"""B11: docs/FINDINGS_EXAMPLES.md - one correct finding per error type, taken from OPEN episodes, with
what each evidence ID is. tests/test_round4_findings_examples.py checks that every example validates against
schemas/findings.schema.json and is a TP on its episode.

    python tools/findings_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TYPES = ["duplicate_invoice", "payment_allocation", "fx_rate", "period_cutoff"]
WHY = {
    "duplicate_invoice": "Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200.",
    "payment_allocation": "Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400.",
    "fx_rate": "Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте.",
    "period_cutoff": "Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте.",
}


def pick():
    from auditenv.cli import episode_dirs

    found = {}
    for split, d in episode_dirs():
        truth = json.loads((d / "grader" / "truth.json").read_text("utf-8"))
        prov = json.loads((d / "grader" / "provenance.json").read_text("utf-8"))
        var = {m["issue_id"]: m.get("variant") for m in prov["mutations"]}
        for iss in truth["issues"]:
            if iss["type"] not in found:
                found[iss["type"]] = (split, d, truth["episode_id"], iss, var[iss["issue_id"]])
    return [found[t] for t in TYPES]


def finding_for(iss: dict) -> dict:
    return {"type": iss["type"], "affected_ids": iss["affected_ids"], "claimed_amount_minor": iss["expected_amount_minor"],
            "currency": iss["currency"], "evidence_ids": iss["evidence_sets"][0], "explanation": WHY[iss["type"]]}


def render() -> str:
    from auditenv.env.data import PublicData
    from auditenv.explain import _describe

    out = ["# Примеры правильных выводов", "",
           "По одному верному выводу на каждый тип ошибки — из **открытых** эпизодов (`episodes/`). Сгенерировано",
           "`python tools/findings_examples.py`; тест проверяет, что каждый пример проходит схему `schemas/findings.schema.json`",
           "и даёт TP на своём эпизоде. Что должно совпасть для TP: тип, `affected_ids` (ровно канонический ID), сумма ±1,",
           "валюта = базовая, и **один набор доказательств целиком** в `evidence_ids`. `explanation` на награду не влияет.", "",
           "Отправка: `{\"tool\": \"submit\", \"args\": {\"findings\": {\"episode_id\": \"…\", \"findings\": [вывод, …]}}}`.",
           "Проверить свой ответ офлайн: `python -m auditenv grade episodes/<split>/<id> my.json`."]
    for split, d, eid, iss, variant in pick():
        data = PublicData.from_dir(d / "public")
        f = finding_for(iss)
        out += ["", f"## `{iss['type']}` (вариант `{variant}`)", "",
                f"Эпизод `episodes/{split}/{eid}`, база {data.base}. {WHY[iss['type']]}", "", "```json",
                json.dumps(f, ensure_ascii=False, indent=1), "```", "", "Доказательства (что вернёт инструмент):", ""]
        out += [f"* `{x}` — {_describe(x, data)}" for x in f["evidence_ids"]]
        if len(iss["evidence_sets"]) > 1:
            out.append(f"* (есть ещё {len(iss['evidence_sets']) - 1} альтернативный набор — подойдёт любой целиком)")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    (ROOT / "docs" / "FINDINGS_EXAMPLES.md").write_text(render(), "utf-8")
    print("findings-examples: wrote docs/FINDINGS_EXAMPLES.md")
