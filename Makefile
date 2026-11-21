# Single verification command: `make check` (or `make docker-check` for the offline container).
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
export PYTHONPATH := $(CURDIR)
export PYTHONHASHSEED := 0
export TZ := UTC

.PHONY: help venv quick test check selfcheck episodes trajectories golden demo docker-build docker-check clean docs-check version finale-preflight exploit-search experiment experiment-v2 verify-independent submission-tag

help:
	@echo "make quick         fast tests + 3 episodes x 4 policies (<30 s)"
	@echo "make check         FULL check: pytest, selfcheck scoreboard, leakscan, replay -> reports/selfcheck.md"
	@echo "make episodes      regenerate 10 train + 10 dev episodes from configs/"
	@echo "make trajectories  regenerate trajectories/trajectories.jsonl"
	@echo "make demo          scripted demo (scripts/demo.sh)"
	@echo "make docs-check    numbers in README/docs match reality (tests, trajectories, episode sizes)"
	@echo "make finale-preflight  offline pre-flight for the finale: image, contract tests, demo (<1 min)"
	@echo "make exploit-search    automatic reward-exploit search (CEM) -> reports/exploit_search.md"
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

verify-independent:
	$(PYTHON) -m auditenv verify-independent --seeds 500

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
