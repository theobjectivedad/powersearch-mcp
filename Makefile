################################################################################
# Configuration
################################################################################

.ONESHELL:
SHELL:=/bin/bash
.SHELLFLAGS=-o errexit -o allexport -o pipefail -o nounset -c

.SILENT:
MAKEFLAGS+=--no-print-directory

WORKSPACE_DIR:=$(CURDIR)
SRC_DIR:=$(WORKSPACE_DIR)/src
VENV_DIR:=$(WORKSPACE_DIR)/.venv
PYTHON_VERSION:=3.13

.PHONY: default
default: help

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  build       Build the package into a distributable format"
	@echo "  clean       Remove build artifacts from previous builds"
	@echo "  init        Create a new virtual environment in '$(VENV_DIR)'"
	@echo "  inspect     Run the MCP Inspector against the local source code"
	@echo "  run-http    Run the application in http mode"
	@echo "  run-stdio   Run the application in stdio mode"
	@echo "  sync        Synchronize the virtual environment with the lockfile"
	@echo "  test        Runs all pre-commit checks for the entire project"
	@echo "  update-deps Update all dependencies to their latest versions"
	@echo "  venv        Alias for the init target"

################################################################################
# Virtual environment
################################################################################

.PHONY: venv
venv: init

.PHONY: init
init:
	if [ -d "$(VENV_DIR)" ]; then \
		echo "ERROR: Virtual environment '$(VENV_DIR)' already exists."; \
		exit 1; \
	fi
	uv venv \
		--python $(PYTHON_VERSION) \
		$(VENV_DIR)
	$(MAKE) sync
	uv run pre-commit install

.PHONY: sync
sync:
	uv pip install --group dev -e $(CURDIR)

################################################################################
# Project management targets.
################################################################################

.PHONY: update-deps
update-deps:
	uv lock --upgrade
	uv sync
	$(MAKE) sync
	uv run pre-commit autoupdate

################################################################################
# Local testing & validation targets
################################################################################

.PHONY: inspector
inspector:
	npx @modelcontextprotocol/inspector --config $(CURDIR)/example-configs/inspector.conf.json

.PHONY: inspect
inspect:
	uv run fastmcp inspect fastmcp.json --format=fastmcp --skip-env

.PHONY: test
test:
	uv run pre-commit run --all-files

################################################################################
# Local run targets
################################################################################

.PHONY: run
run: run-stdio

.PHONY: run-stdio
run-stdio:
	uv run fastmcp run fastmcp.json --skip-source --skip-env

.PHONY: run-http
run-http:
	uv run fastmcp run fastmcp.json --skip-source --skip-env

################################################################################
# Local package build targets
################################################################################

.PHONY: clean
clean:
	rm -rf $(CURDIR)/dist

.PHONY: build
build:
	uv build
