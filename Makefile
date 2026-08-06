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
LIVE ?= 0

WORKDIR := $(if $(strip $(TARGET)),$(TARGET),.)
FORCE_FLAG := $(if $(filter 1 true yes on,$(FORCE)),--force,)
OWNER_FLAG := $(if $(strip $(OWNER)),--owner "$(OWNER)",)
PROJECT_TYPE_FLAG := $(if $(strip $(PROJECT_TYPE)),--project-type "$(PROJECT_TYPE)",)
DRY_RUN_FLAG := $(if $(filter 1 true yes on,$(LIVE)),,--dry-run)

.PHONY: help install dev-install compile test quality check doctor discover require-target require-repo require-project-number init init-dry plan apply setup setup-live labels milestones issues project-create project-sync clean clean-generated

help:
	@echo "GitHub Project Setup"
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
	@echo "  make doctor                          Inspect .env, token and configuration availability"
	@echo "  make clean                           Remove local Python/build artifacts"
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

require-target:
	@test -n "$(TARGET)" || (echo "ERROR: TARGET is required." >&2; echo "  Fix: use TARGET=../my-project" >&2; exit 2)

require-repo:
	@test -n "$(REPO)" || (echo "ERROR: REPO is required." >&2; echo "  Fix: use REPO=owner/repository" >&2; exit 2)

require-project-number:
	@test -n "$(PROJECT_NUMBER)" || (echo "ERROR: PROJECT_NUMBER is required." >&2; echo "  Fix: use PROJECT_NUMBER=1" >&2; exit 2)

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
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup labels sync --repo "$(REPO)" --file config/project/labels.json $(DRY_RUN_FLAG)

milestones: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup milestones sync --repo "$(REPO)" --file config/project/milestones.json $(DRY_RUN_FLAG)

issues: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup issues generate --repo "$(REPO)" --file config/stories/backlog-manifest.json $(DRY_RUN_FLAG)

project-create: require-repo
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project create --repo "$(REPO)" --file config/project/project-definition.json $(DRY_RUN_FLAG)

project-sync: require-repo require-project-number
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project sync --repo "$(REPO)" --project-number "$(PROJECT_NUMBER)" $(OWNER_FLAG) --file config/project/project-definition.json $(DRY_RUN_FLAG)

clean-generated:
	@$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in list(Path('.').rglob('__pycache__'))]; [path.unlink(missing_ok=True) for pattern in ('*.pyc','*.pyo') for path in list(Path('.').rglob(pattern))]"

clean: clean-generated
	@$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(Path(name), ignore_errors=True) for name in ('build','dist','.pytest_cache','.mypy_cache')]; [shutil.rmtree(path, ignore_errors=True) for path in list(Path('.').glob('*.egg-info'))]"
	@echo "Local Python and build artifacts removed."
