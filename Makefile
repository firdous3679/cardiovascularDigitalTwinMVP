PYTHON ?= python

.PHONY: setup test run synth update dashboard

setup:
	$(PYTHON) -m pip install -r requirements.txt

test:
	PYTHONPATH=src $(PYTHON) -m pytest

run:
	PYTHONPATH=src $(PYTHON) -m twin.cli run-baseline

synth:
	PYTHONPATH=src $(PYTHON) -m twin.cli generate-synth

update:
	PYTHONPATH=src $(PYTHON) -m twin.cli update-loop --days $${DAYS:-30}

dashboard:
	PYTHONPATH=src streamlit run app/streamlit_app.py
