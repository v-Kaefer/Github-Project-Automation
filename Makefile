ifeq ($(OS),Windows_NT)
PYTHON ?= python
DETECTED_OS := Windows
else
PYTHON ?= python3
DETECTED_OS := POSIX
endif

PIP ?= $(PYTHON) -m pip
TARGET ?=
REPO ?=
PROFILE ?= core
PROJECT_TYPE ?=
CONFIG ?= project_setup.json
PROJECT_NUMBER ?=
OWNER ?=
FORCE ?= 0
LIVE ?= 0

WORKDIR := $(if $(strip $(TARGET)),$(TARGET),.)
FORCE_FLAG := $(if $(filter 1 true yes on,$(FORCE)),--force,)
OWNER_FLAG := $(if $(strip $(OWNER)),--owner "$(OWNER)",)
PROJECT_TYPE_FLAG := $(if $(strip $(PROJECT_TYPE)),--project-type "$(PROJECT_TYPE)",)
EXECUTION_FLAG := $(if $(filter 1 true yes on,$(LIVE)),--live,--dry-run)

.PHONY: help install dev-install compile test quality check doctor discover init init-dry plan apply setup setup-live labels milestones issues project-create project-sync clean clean-generated

define require_value
$(if $(strip $($(1))),,$(error ERROR: $(1) is required. Fix: $(2)))
endef

help:
	@echo "GitHub Project Setup"
	@echo "Detected environment: $(DETECTED_OS); Python command: $(PYTHON)"
	@echo ""
	@echo "First-time local setup:"
	@echo "  1. Copy .env.example to .env"
	@echo "  2. Add PROJECT_SETUP_PAT when Project v2 operations are needed"
	@echo "  3. Run make doctor"
	@echo "  4. Run make check"
	@echo ""
	@echo "Development:"
	@echo "  make install                         Install the CLI"
	@echo "  make dev-install                     Install in editable mode"
	@echo "  make check                           Validate committed files, compile and run tests"
	@echo "  make doctor                          Inspect OS, .env, gh auth and configuration"
	@echo "  make clean                           Remove local Python/build artifacts"
	@echo ""
	@echo "Repository analysis and setup:"
	@echo "  make discover TARGET=../project REPO=owner/repo"
	@echo "  make discover TARGET=../project REPO=owner/repo PROJECT_TYPE=python"
	@echo "  make init-dry TARGET=../project      Preview copied automation files"
	@echo "  make init TARGET=../project          Copy core automation files"
	@echo "  make init TARGET=../project FORCE=1  Replace existing managed files"
	@echo "  make plan TARGET=../project REPO=owner/repo"
	@echo "  make apply TARGET=../project REPO=owner/repo             Dry-run by default"
	@echo "  make apply TARGET=../project REPO=owner/repo LIVE=1      Apply changes"
	@echo "  make setup TARGET=../project REPO=owner/repo             Init + dry-run"
	@echo "  make setup-live TARGET=../project REPO=owner/repo        Init + live apply"
	@echo ""
	@echo "Individual operations (dry-run by default):"
	@echo "  make labels REPO=owner/repo"
	@echo "  make milestones REPO=owner/repo"
	@echo "  make issues REPO=owner/repo"
	@echo "  make project-create REPO=owner/repo"
	@echo "  make project-sync REPO=owner/repo PROJECT_NUMBER=1"
	@echo "  Add LIVE=1 only after reviewing the dry-run output."

install:
	@echo "==> Installing project_setup"
	$(PIP) install .

dev-install:
	@echo "==> Installing project_setup in editable mode"
	$(PIP) install -e .

quality:
	@echo "==> [1/3] Validating repository structure and committed files"
	$(PYTHON) scripts/validation/repo_quality.py

compile:
	@echo "==> [2/3] Compiling Python sources"
	$(PYTHON) -m compileall -q project_setup scripts tests
	@$(MAKE) --no-print-directory clean-generated
	@echo "Python compilation passed. Generated cache files were removed."

test:
	@echo "==> [3/3] Running unit tests"
	$(PYTHON) -B -m unittest discover -s tests -p "test_*.py" -v

check: quality compile test
	@echo "All repository checks passed. No GitHub API changes were made."

doctor:
	@echo "==> Inspecting local setup (read-only)"
	$(PYTHON) -m project_setup doctor --config "$(CONFIG)"

discover:
	$(call require_value,TARGET,use TARGET=../my-project)
	$(call require_value,REPO,use REPO=owner/repository)
	$(PYTHON) -m project_setup discover --repo "$(REPO)" --config "$(CONFIG)" --root "$(TARGET)" $(PROJECT_TYPE_FLAG) --auto

init:
	$(call require_value,TARGET,use TARGET=../my-project)
	$(PYTHON) -m project_setup init --target "$(TARGET)" --profile "$(PROFILE)" $(FORCE_FLAG) --live

init-dry:
	$(call require_value,TARGET,use TARGET=../my-project)
	$(PYTHON) -m project_setup init --target "$(TARGET)" --profile "$(PROFILE)" $(FORCE_FLAG) --dry-run

plan:
	$(call require_value,REPO,use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup apply --repo "$(REPO)" --config "$(CONFIG)" --dry-run

apply:
	$(call require_value,REPO,use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup apply --repo "$(REPO)" --config "$(CONFIG)" $(EXECUTION_FLAG)

setup: init plan

setup-live:
	$(call require_value,TARGET,use TARGET=../my-project)
	$(call require_value,REPO,use REPO=owner/repository)
	$(MAKE) --no-print-directory init TARGET="$(TARGET)" PROFILE="$(PROFILE)" FORCE="$(FORCE)"
	$(MAKE) --no-print-directory apply TARGET="$(TARGET)" REPO="$(REPO)" CONFIG="$(CONFIG)" LIVE=1

labels:
	$(call require_value,REPO,use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup labels sync --repo "$(REPO)" --file config/project/labels.json $(EXECUTION_FLAG)

milestones:
	$(call require_value,REPO,use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup milestones sync --repo "$(REPO)" --file config/project/milestones.json $(EXECUTION_FLAG)

issues:
	$(call require_value,REPO,use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup issues generate --repo "$(REPO)" --file config/stories/backlog-manifest.json $(EXECUTION_FLAG)

project-create:
	$(call require_value,REPO,use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project create --repo "$(REPO)" --file config/project/project-definition.json $(EXECUTION_FLAG)

project-sync:
	$(call require_value,REPO,use REPO=owner/repository)
	$(call require_value,PROJECT_NUMBER,use PROJECT_NUMBER=1)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project sync --repo "$(REPO)" --project-number "$(PROJECT_NUMBER)" $(OWNER_FLAG) --file config/project/project-definition.json $(EXECUTION_FLAG)

clean-generated:
	@$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in list(Path('.').rglob('__pycache__'))]; [path.unlink(missing_ok=True) for pattern in ('*.pyc','*.pyo') for path in list(Path('.').rglob(pattern))]"

clean: clean-generated
	@$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(Path(name), ignore_errors=True) for name in ('build','dist','.pytest_cache','.mypy_cache')]; [shutil.rmtree(path, ignore_errors=True) for path in list(Path('.').glob('*.egg-info'))]"
	@echo "Local Python and build artifacts removed."
