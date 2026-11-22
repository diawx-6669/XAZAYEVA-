"""Episode generation configs: defaults, validation, config_hash."""

import copy
import json
from pathlib import Path

from .canon import dumps, sha256_hex
from .paths import SCHEMAS_DIR, CONFIGS_DIR

DEFAULT_CONFIG = {
    "name": "default",
    "version": "1.0",
    "base_currencies": ["KZT"],
    "foreign_currencies": ["USD", "EUR"],
    "n_foreign": [1, 2],
    "foreign_share": 0.3,
    "timezones": ["Asia/Almaty", "Asia/Tashkent", "Asia/Dubai", "Asia/Kolkata", "Asia/Tokyo", "America/Bogota"],
    "period_starts": ["2026-07", "2026-08"],
    "period_months": 3,
    "n_entities": [8, 14],
    "n_invoices": [26, 36],
    "line_items": [3, 7],
    "utc_share": [30, 70],
    "distractors": {
        "recurring_rent": 0.5,
        "repeat_amount": 0.4,
        "split_payment": 0.5,
        "multi_invoice_payment": 0.5,
        "partial_open": 0.5,
        "refund": 0.4,
        "bank_fee": 0.5,
        "rounding_residual": 0.4,
        "boundary_time": 0.6,
        "credit_note_reissue": 0.3,
        "unidentified_receipt": 0.3,
        "night_fx": 0.5,
        "overpayment": 0.3,
        "weekend_fx": 0.5,
    },
    "clean_probability": 0.2,
    "n_errors": [1, 4],
    "errors": {"duplicate_invoice": 1.0, "payment_allocation": 1.0, "fx_rate": 1.0, "period_cutoff": 1.0,
               "vat_error": 1.0},
    "interactions": {"partial_fx_cutoff": 0.0, "duplicate_fx": 0.0},
    "min_interactions": 0,
    "fx_variants": {"adjacent_day": 0.35, "utc_date": 0.3, "inverted": 0.05, "historical_rate": 0.15,
                    "wrong_pair": 0.1, "due_date": 0.05},
    "allocation_variants": {"unallocated": 0.4, "partial": 0.4, "wrong_invoice": 0.2},
    "duplicate_variants": {"copy": 0.7, "paid_twice": 0.3},
    "cutoff_variants": {"utc_trap": 0.6, "backdated_posting": 0.2, "prior_period": 0.2},
    "min_lookalikes_per_type": 1,
    "vat_share": 0.35,
    "max_steps": 100,
    "tolerance_minor": 1,
    "max_attempts": 40,
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _schema():
    return json.loads((SCHEMAS_DIR / "config.schema.json").read_text("utf-8"))


class ConfigError(ValueError):
    """A config that is schema-valid but cannot produce the episodes it asks for."""


def validate_config(cfg: dict) -> None:
    from .jsonschema_lite import validate

    try:
        validate(cfg, _schema())
    except ValueError as e:
        raise ConfigError(f"config {cfg.get('name', '?')!r}: {e}") from None
    name = cfg["name"]

    def bad(msg):
        raise ConfigError(f"config {name!r}: {msg}")

    if isinstance(cfg["period_months"], list) and cfg["period_months"][0] > cfg["period_months"][1]:
        bad("period_months: min > max")
    for k in ("n_foreign", "n_entities", "n_invoices", "line_items", "utc_share", "n_errors"):
        lo, hi = cfg[k]
        if lo > hi:
            bad(f"{k}: min > max")
    if cfg["max_steps"] != 100:
        bad("max_steps is fixed to 100 by the case")
    if cfg["utc_share"][1] > 100:
        bad("utc_share is a percentage (0..100)")
    foreign = [c for c in cfg["foreign_currencies"] if c not in cfg["base_currencies"]]
    can_foreign = bool(foreign) and cfg["n_foreign"][1] > 0 and cfg["foreign_share"] > 0
    if cfg["clean_probability"] < 1:
        if cfg["n_errors"][1] == 0:
            bad("n_errors is [.., 0] but clean_probability < 1: set clean_probability to 1 or allow errors")
        weights = {k: v for k, v in cfg["errors"].items() if v > 0}
        inter = any(v > 0 for v in cfg["interactions"].values())
        if not weights and not inter:
            bad("every error weight and every interaction is 0, but clean_probability < 1")
        if not can_foreign and set(weights) <= {"fx_rate"}:
            if weights:
                bad("only fx_rate errors are enabled, but the config has no foreign currency to mis-convert")
            bad("only interaction scenarios are enabled, but they need a foreign currency")
    if cfg["min_interactions"] > sum(1 for v in cfg["interactions"].values() if v > 0):
        bad("min_interactions exceeds the number of enabled interaction scenarios")
    if cfg["min_interactions"] > 0 and not can_foreign:
        bad("interaction scenarios need a foreign currency (both mix FX with another error)")
    if cfg["min_interactions"] > 0 and 2 * cfg["min_interactions"] > max(cfg["n_errors"][1], 2 * cfg["min_interactions"]):
        bad("n_errors too small for the required interaction scenarios (2 issues each)")


def load_config(cfg=None) -> dict:
    """Accepts None, a dict, a path, or a config name from configs/."""
    if cfg is None:
        raw = {}
    elif isinstance(cfg, dict):
        raw = cfg
    else:
        p = Path(cfg)
        if not p.exists():
            p = CONFIGS_DIR / f"{cfg}.json"
        raw = json.loads(p.read_text("utf-8"))
    out = _merge(DEFAULT_CONFIG, raw)
    validate_config(out)
    return out


def config_hash(cfg: dict) -> str:
    return sha256_hex(dumps(cfg).encode("utf-8"))[:16]


# ------------------------------------------------------------------ lock file
def content_hash(cfg: dict) -> str:
    """Hash of the EFFECTIVE config (defaults merged) without its version: changes whenever the generated
    episodes can change - also when a generator default moves under an unchanged config file."""
    body = {k: v for k, v in cfg.items() if k != "version"}
    return sha256_hex(dumps(body).encode("utf-8"))[:16]


def lock_entries() -> list:
    out = []
    for p in sorted(CONFIGS_DIR.glob("*.json")):
        raw = json.loads(p.read_text("utf-8"))
        if not (isinstance(raw, dict) and "name" in raw and "version" in raw):
            continue
        cfg = load_config(p)
        out.append({"name": cfg["name"], "file": p.name, "version": cfg["version"], "config_hash": config_hash(cfg),
                    "content_hash": content_hash(cfg)})
    return out


def check_lock(lock: list) -> list:
    """Problems: content changed but version did not (must bump), or LOCK is stale (must regenerate)."""
    have = {e["name"]: e for e in lock}
    problems = []
    for e in lock_entries():
        old = have.get(e["name"])
        if old is None:
            problems.append(f"{e['name']}: not in configs/LOCK.json (run: python -m auditenv lock-configs)")
        elif old["content_hash"] != e["content_hash"] and old["version"] == e["version"]:
            problems.append(f"{e['name']}: content changed but version is still {e['version']} - bump 'version' "
                            "and add a line to configs/CHANGELOG.md")
        elif old != e:
            problems.append(f"{e['name']}: configs/LOCK.json is stale (run: python -m auditenv lock-configs)")
    gone = set(have) - {e["name"] for e in lock_entries()}
    problems += [f"{n}: in LOCK.json but the config file is gone" for n in sorted(gone)]
    return problems
