PYTHON ?= python
COVERAGE ?= $(if $(wildcard .venv/bin/coverage),.venv/bin/coverage,$(PYTHON) -m coverage)

.PHONY: test coverage cli docker-build docker-smoke ci

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

coverage:
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) erase
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) run -m unittest discover -s tests -v
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) combine
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) report

cli:
	PYTHONPATH=src $(PYTHON) -m leximask.cli --help

docker-build:
	docker build -t leximask:local .

docker-smoke: docker-build
	docker run --rm leximask:local --help
	set -eu; \
	tmp_dir="$$(mktemp -d /tmp/leximask-docker-smoke.XXXXXX)"; \
	trap 'rm -rf "$$tmp_dir"' EXIT; \
	mkdir -p "$$tmp_dir/repo/alpha-service" "$$tmp_dir/repo/runtime/archive"; \
	printf 'source,replacement\nalpha,omega\n' > "$$tmp_dir/mapping.csv"; \
	printf 'alpha token\n' > "$$tmp_dir/repo/alpha-service/alpha.txt"; \
	printf 'binary\n' > "$$tmp_dir/repo/runtime/archive/sample.mp3"; \
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$$tmp_dir:/work" leximask:local plan --input /work/repo --mapping /work/mapping.csv; \
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$$tmp_dir:/work" leximask:local apply --input /work/repo; \
	test -f "$$tmp_dir/repo/omega-service/omega.txt"; \
	grep -q 'omega token' "$$tmp_dir/repo/omega-service/omega.txt"; \
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$$tmp_dir:/work" leximask:local reverse --input /work/repo; \
	test -f "$$tmp_dir/repo/alpha-service/alpha.txt"; \
	grep -q 'alpha token' "$$tmp_dir/repo/alpha-service/alpha.txt"

ci: coverage docker-smoke
