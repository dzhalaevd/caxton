.PHONY: validate

export PATH := $(CURDIR)/.venv/bin:$(PATH)

validate:
	pytest . && ruff check && ruff format && flake8 . --select=WPS && mypy
