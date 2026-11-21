"""Supply chain: third-party notices and an SBOM for the vendored wheels (stdlib only).

Everything is read from the repository itself, so the output is deterministic and offline:
  * every wheel in vendor/wheels/: name, version, licence (from the wheel's METADATA), sha256;
  * every pin in requirements.txt must have exactly one wheel with that version;
  * the base image of the Dockerfile, pinned by digest.

    python tools/third_party.py           -> THIRD_PARTY_NOTICES.md
    python -m auditenv verify-sbom        -> checks reports/sbom.json against the files on disk
    python -m auditenv verify-sbom --write   (re)writes reports/sbom.json
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from email.parser import HeaderParser
from pathlib import Path

from .paths import ROOT

WHEELS = ROOT / "vendor" / "wheels"
SBOM_PATH = ROOT / "reports" / "sbom.json"
NOTICES_PATH = ROOT / "THIRD_PARTY_NOTICES.md"


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def wheel_meta(p: Path) -> dict:
    with zipfile.ZipFile(p) as z:
        name = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        meta = HeaderParser().parsestr(z.read(name).decode("utf-8"))
        lic_files = sorted(n for n in z.namelist() if ".dist-info/" in n and
                           re.search(r"/(licenses/)?(LICEN[CS]E|COPYING|AUTHORS)[^/]*$", n))
    lic = meta.get("License-Expression")
    source = "License-Expression"
    if not lic:
        classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
        lic = meta.get("License") or "; ".join(classifiers) or "UNKNOWN"
        source = "License" if meta.get("License") else "Classifier"
    return {"name": meta["Name"], "version": meta["Version"], "license": lic.strip(), "license_source": source,
            "license_files": [n.split("/", 1)[1] for n in lic_files], "file": p.name, "sha256": sha256_file(p),
            "size": p.stat().st_size, "summary": (meta.get("Summary") or "").strip(),
            "home": (meta.get("Home-page") or next((u.split(",", 1)[1].strip() for u in meta.get_all("Project-URL") or []
                                                      if u.lower().startswith(("homepage", "source"))), "")).strip()}


def wheels() -> list:
    return [wheel_meta(p) for p in sorted(WHEELS.glob("*.whl"))]


def requirements() -> dict:
    out = {}
    for line in (ROOT / "requirements.txt").read_text("utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, ver = line.split("==")
            out[_norm(name)] = ver.strip()
    return out


def base_image() -> dict:
    txt = (ROOT / "Dockerfile").read_text("utf-8")
    m = re.search(r"^FROM\s+(\S+?):(\S+?)@(sha256:[0-9a-f]{64})", txt, re.M)
    return {"name": m.group(1), "tag": m.group(2), "digest": m.group(3)} if m else {}


def build_sbom() -> dict:
    from . import __version__

    comps = [{"type": "container", "name": base_image().get("name", "?"), "version": base_image().get("tag", "?"),
              "hashes": [{"alg": "SHA-256", "content": base_image().get("digest", "").split(":")[-1]}],
              "purl": "pkg:docker/library/{}@{}".format(base_image().get("name", "?"), base_image().get("digest", "")),
              "scope": "required", "description": "base image of the Dockerfile, pinned by digest"}]
    reqs = requirements()
    for w in wheels():
        comps.append({"type": "library", "name": w["name"], "version": w["version"],
                      "licenses": [{"expression": w["license"]}],
                      "hashes": [{"alg": "SHA-256", "content": w["sha256"]}],
                      "purl": f"pkg:pypi/{_norm(w['name'])}@{w['version']}",
                      "properties": [{"name": "auditenv:wheel", "value": w["file"]},
                                     {"name": "auditenv:pinned", "value": str(reqs.get(_norm(w["name"])) == w["version"]).lower()}],
                      "scope": "required"})
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
            "metadata": {"component": {"type": "application", "name": "auditenv", "version": __version__,
                                       "licenses": [{"expression": "MIT"}]},
                         "tools": [{"name": "auditenv.supply", "version": __version__}],
                         "note": "deterministic (no clock or random fields); regenerate with "
                                 "python -m auditenv verify-sbom --write"},
            "components": comps,
            "dependencies": [{"ref": "auditenv", "dependsOn": [f"pkg:pypi/{_norm(w['name'])}@{w['version']}" for w in wheels()]}]}


def verify_sbom(sbom: dict) -> list:
    """Problems (empty list = OK): every wheel on disk is in the SBOM with the same sha256, every SBOM
    component exists on disk, every pin in requirements.txt has its wheel, the base image digest matches."""
    probs = []
    on_disk = {w["file"]: w for w in wheels()}
    seen = set()
    for c in sbom.get("components", []):
        if c["type"] == "container":
            bi = base_image()
            if c["hashes"][0]["content"] != bi.get("digest", "").split(":")[-1]:
                probs.append(f"base image digest differs from Dockerfile: {c['hashes'][0]['content'][:12]}…")
            continue
        f = next((p["value"] for p in c.get("properties", []) if p["name"] == "auditenv:wheel"), None)
        w = on_disk.get(f)
        if w is None:
            probs.append(f"{c['name']} {c['version']}: wheel {f} not in vendor/wheels")
            continue
        seen.add(f)
        if c["hashes"][0]["content"] != w["sha256"]:
            probs.append(f"{f}: sha256 mismatch (sbom {c['hashes'][0]['content'][:12]}…, disk {w['sha256'][:12]}…)")
        if c["version"] != w["version"] or c["licenses"][0]["expression"] != w["license"]:
            probs.append(f"{f}: version/licence differs from the wheel METADATA")
    for f in sorted(set(on_disk) - seen):
        probs.append(f"{f}: on disk but not in the SBOM")
    have = {_norm(w["name"]): w["version"] for w in on_disk.values()}
    for name, ver in sorted(requirements().items()):
        if have.get(name) != ver:
            probs.append(f"requirements.txt pins {name}=={ver}, vendor/wheels has {have.get(name)}")
    return probs


def render_notices() -> str:
    ws = wheels()
    bi = base_image()
    lines = ["# Third-party notices", "",
             "Generated by `python tools/third_party.py` from `requirements.txt`, the wheels in `vendor/wheels/`",
             "(licence = `License-Expression` of the wheel METADATA, else `License`, else the licence classifier) and",
             "the `Dockerfile`. Checked by `tests/test_round4_tools.py::test_third_party_notices_up_to_date` and",
             "`python -m auditenv verify-sbom` (sha256 of every wheel). AuditEnv itself is MIT (`LICENSE`).", "",
             "Only `pytest` and `hypothesis` are direct dependencies (tests); the rest are their pure-Python",
             "dependencies. None of them is imported by the environment or the grader at run time.", "",
             "| Package | Version | Licence | Licence source | Wheel | sha256 |", "|---|---|---|---|---|---|"]
    for w in ws:
        lines.append(f"| {w['name']} | {w['version']} | {w['license']} | {w['license_source']} | `{w['file']}` | `{w['sha256']}` |")
    lines += ["", "## Licence files inside the wheels", ""]
    for w in ws:
        lines.append(f"* **{w['name']}** {w['version']}: " + (", ".join(f"`{x}`" for x in w["license_files"]) or "—")
                     + (f" — {w['home']}" if w["home"] else ""))
    lines += ["", "## Base image", "",
              f"`{bi.get('name')}:{bi.get('tag')}@{bi.get('digest')}` (Docker Official Image; Python is PSF-2.0, Debian",
              "packages under their own licences). It is downloaded once to build the image and is not redistributed",
              "in this repository.", ""]
    return "\n".join(lines)


def main_verify(argv) -> int:
    if "--write" in argv:
        SBOM_PATH.parent.mkdir(parents=True, exist_ok=True)
        SBOM_PATH.write_text(json.dumps(build_sbom(), indent=1, sort_keys=True, ensure_ascii=False) + "\n", "utf-8")
        print(f"verify-sbom: wrote {SBOM_PATH.relative_to(ROOT)}")
    sbom = json.loads(SBOM_PATH.read_text("utf-8"))
    probs = verify_sbom(sbom)
    n = sum(1 for c in sbom["components"] if c["type"] == "library")
    for p in probs:
        print("  " + p)
    print(f"verify-sbom: base image + {n} wheels, {len(probs)} problems")
    return 1 if probs else 0
