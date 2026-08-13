.PHONY: api-compatibility benchmark coverage dependencies imports lint test typecheck validate

API_BASELINE ?=
BENCHMARK_ARGS ?=
GRIFFE_AGAINST := $(if $(strip $(API_BASELINE)),--against $(API_BASELINE),)

validate: lint typecheck dependencies imports coverage

api-compatibility:
	griffe check --search src --format verbose $(GRIFFE_AGAINST) caxton

benchmark:
	pytest tests/test_benchmark_*.py --benchmark-only $(BENCHMARK_ARGS)

lint:
	ruff check --no-fix
	ruff format --check
	flake8 . --select=WPS

typecheck:
	mypy

dependencies:
	deptry src

imports:
	lint-imports

test:
	pytest

coverage:
	coverage erase
	coverage run -m pytest
	coverage report
