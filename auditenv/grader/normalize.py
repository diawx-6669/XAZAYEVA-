"""Open normalization rules (published as part of the grader contract).

- IDs: strip surrounding whitespace, drop duplicates, sort. Case is preserved.
- Currency: strip, upper-case.
- Amount: integer minor units as given (schema guarantees int >= 0).
- explanation: ignored by the matcher and the reward.
"""


def norm_ids(ids) -> list:
    return sorted({str(s).strip() for s in ids if str(s).strip()})


def norm_currency(c: str) -> str:
    return str(c).strip().upper()


def normalize_finding(f: dict) -> dict:
    return {
        "type": f["type"],
        "affected_ids": norm_ids(f["affected_ids"]),
        "claimed_amount_minor": int(f["claimed_amount_minor"]),
        "currency": norm_currency(f["currency"]),
        "evidence_ids": set(norm_ids(f["evidence_ids"])),
    }
