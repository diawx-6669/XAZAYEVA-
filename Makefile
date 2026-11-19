# Single verification command: `make check` (or `make docker-check` for the offline container).
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
export PYTHONPATH := $(CURDIR)
export PYTHONHASHSEED := 0
export TZ := UTC

.PHONY: help venv quick test check selfcheck episodes trajectories golden demo docker-build docker-check clean

help:
	@echo "make quick         fast tests + 3 episodes x 4 policies (<30 s)"
	@echo "make check         FULL check: pytest, selfcheck scoreboard, leakscan, replay -> reports/selfcheck.md"
	@echo "make episodes      regenerate 10 train + 10 dev episodes from configs/"
	@echo "make trajectories  regenerate trajectories/trajectories.jsonl"
	@echo "make demo          scripted demo (scripts/demo.sh)"
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

demo:
	bash scripts/demo.sh

docker-build:
	docker build -t auditenv .

docker-check: docker-build
	docker run --rm --network none --cpus 2 --memory 4g auditenv

clean:
	rm -rf .pytest_cache .hypothesis reports/grader_log.jsonl
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
