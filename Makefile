PYTHON ?= python3
VENV ?= .venv
REPO ?= marcchami/tidgit

PIP := $(VENV)/bin/pip
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
PYTEST := $(VENV)/bin/pytest
BUILD := $(VENV)/bin/python -m build
TWINE := $(VENV)/bin/twine

.PHONY: venv install-dev lint typecheck test check smoke package formula release-artifacts clean

venv:
	$(PYTHON) -m venv $(VENV)

install-dev: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e '.[dev]'

lint:
	$(RUFF) check src tests tidgit

typecheck:
	$(MYPY) src tests

test:
	$(PYTEST) -q

check: lint typecheck test

smoke:
	./tidgit --version
	./tidgit --help

package:
	$(BUILD)
	$(TWINE) check dist/*.whl dist/*.tar.gz

formula: package
	$(PYTHON) scripts/generate_homebrew_formula.py --repo $(REPO) --output Formula/tidgit.rb
	ruby -c Formula/tidgit.rb

release-artifacts: check formula
	sha256sum dist/* > dist/SHA256SUMS.txt

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info src/*.egg-info src/*/*.egg-info
