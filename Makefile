PYTHON ?= python

.PHONY: test cli

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

cli:
	PYTHONPATH=src $(PYTHON) -m leximask.cli --help
