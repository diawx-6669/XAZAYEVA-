# Single verification command: `make check` (or `make docker-check` for the offline container).
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
export PYTHONPATH := $(CURDIR)
export PYTHONHASHSEED := 0
export TZ := UTC

.PHONY: help venv quick test check selfcheck episodes trajectories golden demo docker-build docker-check clean docs-check version finale-preflight exploit-search experiment experiment-v2 mutation verify-independent submission-tag repro-cert repro-cert-check prepublish pii-scan min-budget power

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
	@echo "make power         episodes needed to tell policies apart (paired/unpaired, bootstrap) -> reports/power.md"
	@echo "make min-budget    exact minimal tool calls to see one evidence set per issue, 500 episodes -> reports/min_budget.md"
	@echo "make pii-scan      no real data: cards (Luhn), IBAN, KZ BIN/IIN, e-mail, phones, URLs in 500 episodes + trajectories"
	@echo "make prepublish    read-only report: other branches, secrets in the whole git history, .gitignore, big files"
	@echo "make docker-check  build image and run 'make check' with --network none --cpus 2 --memory 4g"

venv:
	python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt

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

repro-cert-check:
	$(PYTHON) tools/repro_cert.py --check

power:
	$(PYTHON) tools/power.py --n 300

min-budget:
	$(PYTHON) tools/min_budget.py --n 500

pii-scan:
	$(PYTHON) tools/pii_scan.py --n 500

prepublish:
	PYTHON=$(PYTHON) sh scripts/prepublish_check.sh

submission-tag:
	@echo "Run on 22.11 after the final make check (docs/SUBMISSION.md):"
	@echo "  git tag -a v1.0-submission -m 'Genesis Hackathon submission'"
	@echo "  git push origin v1.0-submission"
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
