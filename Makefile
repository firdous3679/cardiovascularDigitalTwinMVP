PYTHON ?= python

.PHONY: setup test run

setup:
	$(PYTHON) -m pip install -r requirements.txt

test:
	PYTHONPATH=src $(PYTHON) -m pytest

run:
	PYTHONPATH=src $(PYTHON) -m twin.cli run-baseline
