# AuditEnv — an RL environment for an AI auditor (short English version)

The full, authoritative documentation is in Russian: [`README.md`](README.md). Jury quick start:
[`docs/JURY.md`](docs/JURY.md).

## What it is

A reproducible simulator for training an AI financial auditor with reinforcement learning. From a
`seed` and a `config` it generates a **fictional** company for one reporting period:

hidden story of events → public documents and double-entry ledger → injected errors with a recorded
cause → closed answer key (`truth.json`).

An agent reads records through five narrow tools (at most 100 steps) and submits findings with
evidence. A grader **outside the agent's process** matches findings to the answer key and computes
the reward. This is an **environment and a grader**, not a model: we train no weights and claim no
model improvement.

* Money is always an `int` in minor units; FX rates are decimal strings computed with `Decimal`,
  `ROUND_HALF_EVEN`. Base currency KZT, USD, JPY (exponent 0) or KWD (exponent 3).
* 4 error types, each one module in `auditenv/generator/errors/`: `duplicate_invoice`,
  `payment_allocation`, `fx_rate`, `period_cutoff` (incl. the UTC trap at the period boundary);
  2 interaction scenarios (`partial_fx_cutoff`, `duplicate_fx`); 14 kinds of *correct* look-alike
  cases; every episode has at least one correct look-alike of every error type.
* Tools: `list_records(table, cursor, limit≤50)`, `get_record(table, id)`, `get_document(doc_id)`,
  `calculator(expression)` (AST, `Decimal`, no names or powers), `submit(findings)`.
  Errors are bare codes (`unknown_tool | bad_args | not_found | invalid_cursor | calc_error |
  episode_over`) and every error costs a step.
* Reward: `clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)` after one-to-one matching (same type,
  exact affected IDs, amount within tolerance, same currency, one full evidence set). An
  "experimental" reward that also requires the evidence to have actually been observed is reported
  separately.

## Run

```bash
make docker-check
```

Builds the image (`python:3.11-slim` pinned by digest, dependencies from `vendor/wheels/`, no
network) and runs the full check with the jury limits:
`docker run --rm --network none --cpus 2 --memory 4g auditenv`. Without Docker:

```bash
make venv
```

```bash
make check
```

Other entry points: `make quick` (fast tests + 3 episodes × 4 policies), `make demo`,
`make mutation` (grader mutation testing → `reports/mutation.md`), `make experiment-v2`
(pre-registered learnable-signal experiment, `docs/EXPERIMENT_v2.md`).

```python
import auditenv
env = auditenv.make("dev-mixed", mode="train")      # "eval": reward 0, info {}, result only in the grader log
obs, info = env.reset(seed=7)
obs, reward, terminated, truncated, info = env.step({"tool": "list_records", "args": {"table": "ledger"}})
```

Your own agent, as any program speaking JSON lines (protocol: `docs/ADAPTER.md`):

```bash
python -m auditenv run --policy-cmd "python examples/minimal_agent.py" --seed 12 --config dev-mixed
```

Closed episodes for the jury: set a secret `AUDITENV_SEED_SALT`; `run --seed …` then generates the
episode in the evaluator's memory only. Twenty paired transforms (shuffled rows + opaque IDs) for any
policy in one command: `python -m auditenv jury-pairs --policy-cmd "python my_policy.py" --n 20`.

## Architecture

```
seed, config ─► generator/story.py ─► generator/books.py ─► generator/errors/* + interactions.py
                 (hidden events)       (documents + ledger)   (mutations, before/after in provenance)
                                                                  │
        public/  manifest.json ledger.csv invoices.jsonl payments.jsonl fx.csv policy.json
        grader/  truth.json provenance.json              (never visible to the agent)
                                                                  │
agent process ◄── JSON lines ──► env/env.py (tools, cursors, calculator, step limit)
 (sandbox: python -I -S, empty cwd,                                │ submit
  3 env vars, rlimits, nobody)                    grader/ schema → normalize → matcher → reward → log
```

Independent checks that do not trust the generator: `tools/verify_independent.py` (stdlib only,
run with `python -I`, re-derives every error from the public files), `verify-provenance` (undo and
replay every mutation), a coincidence scanner that regenerates an episode if the solver finds
anything in a clean book, `leakscan` over all trajectories, and a hash-chained grader log.

## Scoreboard

`make check` prints a jury-style scoreboard and writes `reports/selfcheck.md`:

| Block | Checks | Points |
|---|---|---|
| Contract and isolation | 20/20 | 25 / 25 |
| Data and answer key | 20/20 | 25 / 25 |
| Reward robustness | 20/20 | 25 / 25 |
| Reproducibility and generalisation | 20/20 | 15 / 15 |
| **Total** (the 10 "engineering" points are the jury's) | | **90 / 90** |

plus diagnostics (P/R/F1 macro and micro, reward on clean vs erroneous books, steps, time) for the
four reference policies (`random_explorer`, `simple_reconcile`, `flag_all`, `oracle`) and 11 attacks
(twins, type and amount brute force, guessed IDs, evidence spam, junk explanation, wrong currency, …).
Mapping "case requirement → file → test": the table in [`README.md`](README.md); section-10 checks →
commands: [`docs/JURY.md`](docs/JURY.md).

## Trust card and round-4 tools

| What was checked | Result | Where |
|---|---|---|
| Jury-style scoreboard | <!--fact:selfcheck_total-->90/90<!--/fact--> | `make check` → `reports/selfcheck.md` |
| Tests (pytest + hypothesis) | <!--fact:n_tests-->659<!--/fact--> | `make check` |
| Deliberate grader bugs caught by the tests | <!--fact:mutation_killed-->23/23<!--/fact--> | `make mutation` |
| Independent verifier (no `import auditenv`) | <!--fact:verify_independent_episodes-->540<!--/fact--> episodes, 0 disagreements | `make check` |
| Black-box jury simulation (own policies and grader) | <!--fact:jury_sim_open-->0<!--/fact--> open findings | `reports/jury_sim.md` |
| Vulnerabilities found and closed, each with a guard test | <!--fact:failures_closed-->18<!--/fact--> | `docs/FAILURES.md` |
| Exhaustive small-case enumeration of the grader | 85 008 cases, 0 violations | `make exhaustive` |
| Same hashes on Python 3.11 / 3.12 / 3.13, different hash seeds, time zones, locales | 9/9 runs | `make repro-cross` |
| No real personal or financial data (cards, IBAN, KZ BIN/IIN, e-mail, phones, URLs) | 0 hits on 520 episodes | `make pii-scan`, `docs/SAFETY.md` |

Round-4 commands (outside `make check` unless noted): `make repro-cert` (reproducibility certificate,
compare machines), `make prepublish` (secrets in the whole git history, read-only), `make min-budget`
(exact minimal tool calls per evidence set: median 5, max 13 of 100), `make power` (episodes needed to tell
policies apart), `make difficulty` (Rasch difficulty of error variants), `make coverage-map` (pairwise
coverage of generator factors), `make sensitivity` (tolerance and step-cost sensitivity), `make ablation`
(reward without the evidence requirement), `make bench` (multiprocessing env pool), `make verify-release`,
`make offline-kit`. Grader-side tools for open episodes: `python -m auditenv grade <episode> <findings.json>`
(reason code per finding) and `python -m auditenv explain <episode>` (before/after HTML, examples in
`site/explain/`). For LLM agents: tool schemas for OpenAI and Anthropic function calling, a system prompt
and two few-shot transcripts in `tools/llm/`; a Gymnasium wrapper in `examples/gym_wrapper.py`.
Short design note: `docs/DESIGN_SHORT.md`; FAQ: `docs/FAQ.md`; agent author guide: `docs/AGENT_GUIDE.md`;
forecast written before the jury run: `docs/PREDICTION.md`.

## Limitations (short; full list in `docs/LIMITATIONS.md`)

* A high reward means "found the distortions this generator planted, with the required evidence" —
  not fitness for real-world audit. All companies, people and money are fictional.
* A narrow world: 4 error types, 7 accounts, 5 currencies, fixed-offset time zones (no DST), no VAT,
  no holidays in the FX calendar (business days = Mon–Fri).
* The generator, the solver and the independent verifier were written by the same team: a shared
  misreading of a rule would not be caught by code; `docs/MANUAL_AUDIT.md` is the human cross-check.
* Process isolation is layered (non-dumpable evaluator, rlimits, `nobody` when run as root) but is
  not a full sandbox: no seccomp, no network or filesystem namespaces.
* `simple_reconcile` is intentionally simple (`docs/FAILURES.md`) and scores about −1 on clean books.

License: MIT.
