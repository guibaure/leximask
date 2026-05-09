PYTHON ?= python
COVERAGE ?= $(if $(wildcard .venv/bin/coverage),.venv/bin/coverage,$(PYTHON) -m coverage)
SETUPTOOLS_PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,$(PYTHON))

.PHONY: test coverage compile package-smoke cli docker-build docker-smoke ci

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

coverage:
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) erase
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) run -m unittest discover -s tests -v
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) combine
	COVERAGE_FILE=/tmp/leximask.coverage PYTHONPATH=src $(COVERAGE) report

compile:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests

package-smoke:
	set -eu; \
	tmp_dir="$$(mktemp -d /tmp/leximask-package-smoke.XXXXXX)"; \
	trap 'rm -rf "$$tmp_dir"' EXIT; \
	build_backend_site="$$( $(SETUPTOOLS_PYTHON) -c 'import pathlib, setuptools; print(pathlib.Path(setuptools.__file__).parent.parent)' )"; \
	$(PYTHON) -m venv "$$tmp_dir/build-venv"; \
	PIP_CACHE_DIR="$$tmp_dir/pip-cache" PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONPATH="$$build_backend_site" "$$tmp_dir/build-venv/bin/python" -m pip wheel . --no-deps --no-build-isolation --wheel-dir "$$tmp_dir/dist" >/dev/null; \
	$(PYTHON) -m venv "$$tmp_dir/run-venv"; \
	PIP_CACHE_DIR="$$tmp_dir/pip-cache" PIP_DISABLE_PIP_VERSION_CHECK=1 "$$tmp_dir/run-venv/bin/python" -m pip install --no-index --find-links "$$tmp_dir/dist" leximask >/dev/null; \
	PIP_CACHE_DIR="$$tmp_dir/pip-cache" PIP_DISABLE_PIP_VERSION_CHECK=1 "$$tmp_dir/run-venv/bin/python" -m pip check; \
	mkdir -p "$$tmp_dir/repo/alpha"; \
	printf 'source,replacement\nalpha,omega\n' > "$$tmp_dir/mapping.csv"; \
	printf 'alpha token\n' > "$$tmp_dir/repo/alpha/alpha.txt"; \
	"$$tmp_dir/run-venv/bin/leximask" plan --input "$$tmp_dir/repo" --mapping "$$tmp_dir/mapping.csv" >/dev/null; \
	"$$tmp_dir/run-venv/bin/leximask" apply --input "$$tmp_dir/repo" >/dev/null; \
	test -f "$$tmp_dir/repo/omega/omega.txt"; \
	grep -q 'omega token' "$$tmp_dir/repo/omega/omega.txt"; \
	"$$tmp_dir/run-venv/bin/leximask" reverse --input "$$tmp_dir/repo" >/dev/null; \
	test -f "$$tmp_dir/repo/alpha/alpha.txt"; \
	grep -q 'alpha token' "$$tmp_dir/repo/alpha/alpha.txt"

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

ci: compile coverage package-smoke docker-smoke
