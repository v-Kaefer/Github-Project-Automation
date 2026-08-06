PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
TARGET ?=
REPO ?=
PROFILE ?= core
PROJECT_TYPE ?=
CONFIG ?= project_setup.json
PROJECT_NUMBER ?=
OWNER ?=
FORCE ?= 0

WORKDIR := $(if $(strip $(TARGET)),$(TARGET),.)
FORCE_FLAG := $(if $(filter 1 true yes on,$(FORCE)),--force,)
OWNER_FLAG := $(if $(strip $(OWNER)),--owner "$(OWNER)",)
PROJECT_TYPE_FLAG := $(if $(strip $(PROJECT_TYPE)),--project-type "$(PROJECT_TYPE)",)

.PHONY: help install dev-install compile test quality check doctor discover require-target require-repo require-project-number init init-dry plan apply setup setup-live labels milestones issues project-create project-sync clean

help:
	@echo "GitHub Project Setup"
	@echo ""
	@echo "Development:"
	@echo "  make install                         Install the CLI"
	@echo "  make dev-install                     Install in editable mode"
	@echo "  make check                           Compile, validate and run tests"
	@echo "  make doctor                          Inspect local configuration"
	@echo ""
	@echo "Repository analysis and setup:"
	@echo "  make discover TARGET=../project REPO=owner/repo"
	@echo "  make discover TARGET=../project REPO=owner/repo PROJECT_TYPE=python"
	@echo "  make init TARGET=../project          Copy core automation files"
	@echo "  make init TARGET=../project PROFILE=godot"
	@echo "  make init TARGET=../project FORCE=1  Replace existing managed files"
	@echo "  make plan TARGET=../project REPO=owner/repo"
	@echo "  make apply TARGET=../project REPO=owner/repo"
	@echo "  make setup TARGET=../project REPO=owner/repo       Init + dry-run"
	@echo "  make setup-live TARGET=../project REPO=owner/repo  Init + live apply"
	@echo ""
	@echo "Individual operations:"
	@echo "  make labels REPO=owner/repo"
	@echo "  make milestones REPO=owner/repo"
	@echo "  make issues REPO=owner/repo"
	@echo "  make project-create REPO=owner/repo"
	@echo "  make project-sync REPO=owner/repo PROJECT_NUMBER=1"

install:
	$(PIP) install .

dev-install:
	$(PIP) install -e .

compile:
	$(PYTHON) -m compileall -q project_setup scripts tests

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

quality:
	$(PYTHON) scripts/validation/repo_quality.py

check: compile quality test

doctor:
	$(PYTHON) -m project_setup doctor --config "$(CONFIG)"

require-target:
	@test -n "$(TARGET)" || (echo "TARGET is required, for example: make init TARGET=../my-project" >&2; exit 2)

require-repo:
	@test -n "$(REPO)" || (echo "REPO is required, for example: REPO=owner/repository" >&2; exit 2)

require-project-number:
	@test -n "$(PROJECT_NUMBER)" || (echo "PROJECT_NUMBER is required" >&2; exit 2)

discover: require-target require-repo
	$(PYTHON) -m project_setup discover --repo "$(REPO)" --config "$(CONFIG)" --root "$(TARGET)" $(PROJECT_TYPE_FLAG) --auto

init: require-target
	$(PYTHON) -m project_setup init --target "$(TARGET)" --profile "$(PROFILE)" $(FORCE_FLAG)

init-dry: require-target
	$(PYTHON) -m project_setup init --target "$(TARGET)" --profile "$(PROFILE)" $(FORCE_FLAG) --dry-run

plan: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup apply --repo "$(REPO)" --config "$(CONFIG)" --dry-run

apply: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup apply --repo "$(REPO)" --config "$(CONFIG)" --no-dry-run

setup: init plan

setup-live: init apply

labels: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup labels sync --repo "$(REPO)" --file config/project/labels.json --dry-run

milestones: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup milestones sync --repo "$(REPO)" --file config/project/milestones.json --dry-run

issues: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup issues generate --repo "$(REPO)" --file config/stories/backlog-manifest.json --dry-run

project-create: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project create --repo "$(REPO)" --file config/project/project-definition.json --dry-run

project-sync: require-repo require-project-number
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project sync --repo "$(REPO)" --project-number "$(PROJECT_NUMBER)" $(OWNER_FLAG) --file config/project/project-definition.json --dry-run

clean:
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true
	@rm -rf build dist *.egg-info .pytest_cache .mypy_cache
