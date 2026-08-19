.PHONY: benchmark coverage

BENCHMARK_ARGS ?=

benchmark:
	pytest tests/test_benchmark_*.py --benchmark-only $(BENCHMARK_ARGS)

coverage:
	coverage erase
	coverage run -m pytest
	coverage report
