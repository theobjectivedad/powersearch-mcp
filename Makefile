################################################################################
# Makefile Configuration
################################################################################

.ONESHELL:
SHELL:=/bin/bash
.SHELLFLAGS=-o errexit -o allexport -o pipefail -o nounset -c

.SILENT:
MAKEFLAGS+=--no-print-directory

WORKSPACE_DIR:=$(CURDIR)
SRC_DIR:=$(WORKSPACE_DIR)/src
VENV_DIR:=$(WORKSPACE_DIR)/.venv
VENV_PYTHON:=$(VENV_DIR)/bin/python
PYTHON_VERSION:=3.13

.PHONY: default
default: sync

.PHONY: init
init:
	if [ -d "$(VENV_DIR)" ]; then \
		echo "ERROR: Virtual environment '$(VENV_DIR)' already exists, delete it first if you really want to run this target."; \
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

.PHONY: update-deps
update-deps:
	uv lock --upgrade
	uv sync
	$(MAKE) sync
	uv run pre-commit autoupdate

.PHONY: inspect
inspect:
	npx @modelcontextprotocol/inspector --config $(CURDIR)/inspector.conf.json
