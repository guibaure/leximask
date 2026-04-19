PYTHON ?= python

.PHONY: test cli docker-build ci

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

cli:
	PYTHONPATH=src $(PYTHON) -m leximask.cli --help

docker-build:
	docker build -t leximask:local .

ci: test docker-build
