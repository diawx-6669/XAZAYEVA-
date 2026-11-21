"""A8: pre-publication report - read-only, deletes nothing.

    sh scripts/prepublish_check.sh      (= make prepublish)

1. branches other than main (local and remote) - for MANUAL deletion before the repo is made public;
2. the WHOLE git history (all refs, every patch) scanned for secrets: tokens and keys of common services,
   private keys, a real value after AUDITENV_SEED_SALT=, files under jury_sim/work/ (the salt of the jury
   simulation lives there);
3. .gitignore covers jury_sim/work/ and the temporary report files;
4. blobs larger than 5 MB anywhere in the history.
Exit code 1 if 2-4 find anything (the branch list alone is informational).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIG = 5 * 1024 * 1024

SECRET_PATTERNS = [
    ("github_token", r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("private_key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    ("slack_token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("openai_key", r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}"),
    ("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    ("google_api_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("telegram_bot_token", r"\b\d{8,10}:AA[0-9A-Za-z_-]{33}\b"),
    # a concrete salt value; placeholders (<...>, $VAR, '', "...", secret/секрет words) are allowed
    ("seed_salt_value", r"AUDITENV_SEED_SALT=(?![\"']?(?:<|\$|\"|'|\s|$|\{|\.\.\.|секрет|secret|SECRET|xxx|x{3}))[\"']?[A-Za-z0-9_+/=-]{6,}"),
]
FORBIDDEN_PATHS = [r"^jury_sim/work/", r"(^|/)\.env$", r"(^|/)credentials\.json$", r"\.pem$", r"(^|/)id_rsa$",
                   r"(^|/)salt\.txt$"]
GITIGNORE_NEEDS = {"jury_sim/work/": ["jury_sim/work/", "work/"], ".venv/": [".venv/"],
                   "reports/repro_certificate_ci.json": ["reports/repro_certificate_ci.json"],
                   "reports/tmp/": ["reports/tmp/"]}


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, errors="replace", check=True).stdout


def branches() -> list:
    out = [b.strip().lstrip("* ").strip() for b in git("branch", "-a", "--format=%(refname:short)").splitlines()]
    return sorted(b for b in out if b and b not in ("main", "origin/main", "origin/HEAD", "origin") and "HEAD" not in b)


def scan_history() -> list:
    found = []
    log = git("log", "--all", "-p", "--no-color", "--no-ext-diff", "--format=@@COMMIT %h", "-U0")
    commit, fname = "?", "?"
    for line in log.splitlines():
        if line.startswith("@@COMMIT "):
            commit = line.split()[1]
        elif line.startswith("+++ b/"):
            fname = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for name, pat in SECRET_PATTERNS:
                if re.search(pat, line):
                    found.append(f"{name}: commit {commit} {fname}: {line[1:80].strip()}")
    for line in git("log", "--all", "--name-only", "--format=@@COMMIT %h").splitlines():
        if line.startswith("@@COMMIT "):
            commit = line.split()[1]
        elif line.strip():
            for pat in FORBIDDEN_PATHS:
                if re.search(pat, line.strip()):
                    found.append(f"forbidden_path: commit {commit}: {line.strip()}")
    return sorted(set(found))


def gitignore_gaps() -> list:
    lines = []
    for p in [ROOT / ".gitignore", *ROOT.glob("*/.gitignore")]:
        rel = p.parent.relative_to(ROOT).as_posix()
        for ln in p.read_text("utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                lines.append(ln if rel == "." else f"{rel}/{ln}")
    gaps = []
    for need, alts in GITIGNORE_NEEDS.items():
        if not any(x in lines or x.lstrip("/") in [l.lstrip("/") for l in lines] for x in alts + [need]):
            gaps.append(f".gitignore does not cover {need}")
    tracked = git("ls-files").splitlines()
    for t in tracked:
        if t.startswith("jury_sim/work/") or t.startswith("reports/tmp/"):
            gaps.append(f"tracked file that should be ignored: {t}")
    return gaps


def big_blobs() -> list:
    objs = git("rev-list", "--objects", "--all")
    p = subprocess.run(["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)"], cwd=ROOT,
                       input=objs, capture_output=True, text=True, check=True)
    out = []
    for line in p.stdout.splitlines():
        typ, sha, size, *rest = line.split(" ", 3)
        if typ == "blob" and int(size) > BIG:
            out.append(f"{(rest or ['?'])[0]} ({int(size) / 1048576:.1f} MB, blob {sha[:10]})")
    return sorted(out)


def allowlist() -> list:
    p = ROOT / "tools" / "prepublish_allow.txt"
    out = []
    for ln in p.read_text("utf-8").splitlines() if p.exists() else []:
        if ln.strip() and not ln.startswith("#") and "|" in ln:
            sub, why = ln.split("|", 1)
            out.append((sub.strip(), why.strip()))
    return out


def split_allowed(findings: list, allow: list) -> tuple[list, list]:
    keep, allowed = [], []
    for f in findings:
        why = next((w for s, w in allow if s in f), None)
        (allowed if why else keep).append(f if not why else f"{f}  [allowed: {why}]")
    return keep, allowed


def main() -> int:
    allow = allowlist()
    br = branches()
    sec, sec_ok = split_allowed(scan_history(), allow)
    ign = gitignore_gaps()
    big, big_ok = split_allowed(big_blobs(), allow)
    n_commits = len(git("rev-list", "--all").splitlines())
    print("== prepublish (read-only report; nothing is deleted) ==")
    print(f"1. branches other than main: {len(br)} (delete by hand if not needed: git push origin --delete <name>)")
    for b in br:
        print(f"   - {b}")
    print(f"2. secrets in the whole history ({n_commits} commits, all refs): {len(sec)}")
    for s in sec:
        print(f"   ! {s}")
    for s in sec_ok:
        print(f"   ~ {s}")
    print(f"3. .gitignore: {len(ign)} gaps")
    for g in ign:
        print(f"   ! {g}")
    print(f"4. blobs > 5 MB in history: {len(big)}")
    for b in big:
        print(f"   ! {b}")
    for b in big_ok:
        print(f"   ~ {b}")
    n = len(sec) + len(ign) + len(big)
    print(f"prepublish: {n} findings ({len(sec_ok) + len(big_ok)} reviewed and allowed in tools/prepublish_allow.txt)")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
