# One-command entry points for local development and CI.
# On Windows without make, run the commands in each recipe directly.

.PHONY: install dev-api dev-web lint test coverage benchmark frontend-check check

install:
	pip install -r requirements-dev.txt
	npm --prefix frontend ci

dev-api:
	uvicorn api.main:app --reload

dev-web:
	npm --prefix frontend run dev

lint:
	ruff check .

test:
	pytest

coverage:
	pytest --cov --cov-report=term

benchmark:
	python benchmarks/run_backtest_benchmark.py --fail-on-p95-ms 100

frontend-check:
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck
	npm --prefix frontend test
	npm --prefix frontend run build

# Everything CI runs, except the container check.
check: lint coverage benchmark frontend-check
