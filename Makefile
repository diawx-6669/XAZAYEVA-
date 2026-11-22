# Single verification command: `make check` (or `make docker-check` for the offline container).
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
export PYTHONPATH := $(CURDIR)
export PYTHONHASHSEED := 0
export TZ := UTC

.PHONY: help venv quick test check selfcheck episodes trajectories golden demo docker-build docker-check clean docs-check version finale-preflight exploit-search experiment experiment-v2 mutation verify-independent submission-tag repro-cert repro-cert-check repro-cross prepublish pii-scan min-budget power difficulty bench coverage-map exhaustive sensitivity ablation verify-release offline-kit targets-timing jury-salts shortcut-probe benford

help:
	@echo "make quick         fast tests + 3 episodes x 4 policies (<30 s)"
	@echo "make check         FULL check: pytest, selfcheck scoreboard, leakscan, replay -> reports/selfcheck.md"
	@echo "make episodes      regenerate 10 train + 10 dev episodes from configs/"
	@echo "make trajectories  regenerate trajectories/trajectories.jsonl"
	@echo "make demo          scripted demo (scripts/demo.sh)"
	@echo "make docs-check    numbers in README/docs match reality (tests, trajectories, episode sizes)"
	@echo "make finale-preflight  offline pre-flight for the finale: image, contract tests, demo (<1 min)"
	@echo "make exploit-search    automatic reward-exploit search (CEM) -> reports/exploit_search.md"
	@echo "make mutation      hand-written grader mutations vs fast tests -> reports/mutation.md (not in check)"
	@echo "make repro-cert    reproducibility certificate (20 episode hashes + deterministic selfcheck); repro-cert-check compares"
	@echo "make ablation      the same answers graded with and without the evidence requirement -> reports/ablation_evidence.md"
	@echo "make sensitivity   reward vs tolerance 0/1/2/5/100 and vs step cost -> reports/tolerance.md, reports/step_cost.md"
	@echo "make exhaustive    all small grading cases (8 truths x 10626 answers): dominance, monotonicity, order, step cost"
	@echo "make coverage-map  pairwise coverage of generator factors on 1000 seeds, SVG heat map, uncovered pairs with reasons"
	@echo "make bench         env pool (multiprocessing): steps/s, episodes/s, memory, 1 vs 2 workers, 200/1000/2000 rows -> reports/bench.md"
	@echo "make difficulty    Rasch difficulty of every error variant on a panel of 10 simple_reconcile variants -> reports/difficulty.md"
	@echo "make power         episodes needed to tell policies apart (paired/unpaired, bootstrap) -> reports/power.md"
	@echo "make min-budget    exact minimal tool calls to see one evidence set per issue, 500 episodes -> reports/min_budget.md"
	@echo "make pii-scan      no real data: cards (Luhn), IBAN, KZ BIN/IIN, e-mail, phones, URLs in 500 episodes + trajectories"
	@echo "make prepublish    read-only report: other branches, secrets in the whole git history, .gitignore, big files"
	@echo "make venv          .venv with the pinned wheels from vendor/wheels (offline)"
	@echo "make test          full pytest only (make check runs it too)"
	@echo "make selfcheck     scoreboard only -> reports/selfcheck.md"
	@echo "make golden        rewrite tests/golden_hashes.json (only after an intended generator change)"
	@echo "make verify-independent  independent verifier on committed + selfcheck + 500 fresh episodes"
	@echo "make experiment    optional E6 experiment (docs/EXPERIMENT.md); experiment-v2: docs/EXPERIMENT_v2.md"
	@echo "make experiment-v2 E6 v2 on the current generator (new salt)"
	@echo "make repro-cert-check  recompute the reproducibility certificate and compare with the committed one"
	@echo "make verify-release  ready to tag? clean tree, tag = HEAD, selfcheck from this code, certificate, SBOM, docs, prepublish"
	@echo "make jury-salts    black-box jury simulation (closed run + 20 contract checks) under 8 salts -> reports/jury_salts.md"
	@echo "make targets-timing  run the round-4 targets once and record their wall time -> reports/targets_timing.md"
	@echo "make offline-kit   dist/: zip of the repo at the tag + saved Docker image + SHA256SUMS for the offline finale"
	@echo "make shortcut-probe  can format-only features (position, ID rank, seconds, UTC style) find the errors? + positive control"
	@echo "make benford       first digits of amounts vs Benford (realism) and errors vs clean rows (no shortcut)"
	@echo "make submission-tag    print the tag commands and the SHA for the form (docs/SUBMISSION.md)"
	@echo "make docker-build  build the image only; make version writes VERSION (commit for the report header)"
	@echo "make version       write VERSION = short commit id"
	@echo "make clean         remove caches and the local grader log"
	@echo "make repro-cross   the certificate under every Python 3.11+ on PATH x 3 environments -> reports/repro_cross_python.md"
	@echo "make docker-check  build image and run 'make check' with --network none --cpus 2 --memory 4g"

venv:
	python3.11 -m venv .venv && .venv/bin/pip install --no-index --find-links vendor/wheels --no-deps -r requirements.txt

quick:
	$(PYTHON) -m pytest -q -m "not slow" -x
	$(PYTHON) -m auditenv quick

test:
	$(PYTHON) -m pytest -q

selfcheck:
	$(PYTHON) -m auditenv.selfcheck

check:
	PYTHON=$(PYTHON) sh scripts/check.sh

episodes:
	$(PYTHON) -m auditenv export

trajectories:
	$(PYTHON) -m auditenv trajectories
	$(PYTHON) -m auditenv leakscan

golden:
	$(PYTHON) -m auditenv golden

docs-check:
	$(PYTHON) -m auditenv docs-check

finale-preflight:
	sh scripts/finale_preflight.sh

exploit-search:
	$(PYTHON) -m auditenv exploit-search

experiment:
	$(PYTHON) -m auditenv experiment

experiment-v2:
	$(PYTHON) -m auditenv experiment --protocol E6v2

mutation:
	$(PYTHON) tools/mutation_test.py

verify-independent:
	$(PYTHON) -m auditenv verify-independent --seeds 500

repro-cert:
	$(PYTHON) tools/repro_cert.py

repro-cross:
	$(PYTHON) tools/repro_cross.py

repro-cert-check:
	$(PYTHON) tools/repro_cert.py --check

ablation:
	$(PYTHON) tools/ablation_evidence.py --n 120

sensitivity:
	$(PYTHON) tools/sensitivity.py --n 120

exhaustive:
	$(PYTHON) tools/reward_exhaustive.py full

coverage-map:
	$(PYTHON) tools/coverage_map.py --n 1000

bench:
	$(PYTHON) examples/env_pool.py

difficulty:
	$(PYTHON) tools/rasch.py --n 300

power:
	$(PYTHON) tools/power.py --n 300

min-budget:
	$(PYTHON) tools/min_budget.py --n 500

pii-scan:
	$(PYTHON) tools/pii_scan.py --n 500

prepublish:
	PYTHON=$(PYTHON) sh scripts/prepublish_check.sh

verify-release:
	$(PYTHON) tools/verify_release.py

jury-salts:
	$(PYTHON) tools/jury_salts.py --n 8

targets-timing:
	$(PYTHON) tools/time_targets.py

offline-kit:
	sh scripts/offline_kit.sh

benford:
	$(PYTHON) tools/benford.py

shortcut-probe:
	$(PYTHON) tools/shortcut_probe.py

submission-tag:
	@echo "Run on 22.11 after the final make check (docs/SUBMISSION.md):"
	@echo "  git tag -a v1.2-submission -m 'Genesis Hackathon submission'"
	@echo "  git push origin v1.2-submission"
	@git log -1 --format='  SHA for the form: %H'

version:
	@git rev-parse --short=12 HEAD > VERSION 2>/dev/null || echo unknown > VERSION; cat VERSION

demo:
	bash scripts/demo.sh

docker-build: version
	docker build -t auditenv .

docker-check: docker-build
	docker run --rm --network none --cpus 2 --memory 4g auditenv

clean:
	rm -rf .pytest_cache .hypothesis reports/grader_log.jsonl
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
