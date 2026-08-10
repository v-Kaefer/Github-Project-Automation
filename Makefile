ifeq ($(OS),Windows_NT)
PYTHON ?= python
DETECTED_OS := Windows
else
PYTHON ?= python3
DETECTED_OS := POSIX
endif

PIP ?= $(PYTHON) -m pip
SOURCE_MARKER := .project-setup-source
TOOL_REPOSITORY := $(shell $(PYTHON) -c "from pathlib import Path; p=Path('$(SOURCE_MARKER)'); print(1 if p.is_file() and p.read_text(encoding='utf-8').strip() == 'github-project-setup-source' else 0)")
REPOSITORY_MODE := $(if $(filter 1,$(TOOL_REPOSITORY)),tool-source,embedded-target)
COMPILE_PATHS := project_setup scripts/validation $(if $(filter 1,$(TOOL_REPOSITORY)),tests,)

# Resolve persistent defaults through the same Python .env loader used by the CLI.
# Only Make command-line variables override these values; unrelated process-level
# variables such as TARGET or REPO are intentionally ignored to avoid collisions.
ENV_TARGET := $(shell $(PYTHON) -c "from project_setup.github import load_env_file; import os; load_env_file(); print(os.getenv('PROJECT_SETUP_TARGET', ''))")
ENV_REPO := $(shell $(PYTHON) -c "from project_setup.github import load_env_file; import os; load_env_file(); print(os.getenv('GITHUB_REPOSITORY', ''))")
ENV_CONFIG := $(shell $(PYTHON) -c "from project_setup.github import load_env_file; import os; load_env_file(); print(os.getenv('PROJECT_SETUP_CONFIG', ''))")
ENV_PROJECT_NUMBER := $(shell $(PYTHON) -c "from project_setup.github import load_env_file; import os; load_env_file(); print(os.getenv('PROJECT_SETUP_PROJECT_NUMBER', ''))")
ENV_OWNER_TYPE := $(shell $(PYTHON) -c "from project_setup.github import load_env_file; import os; load_env_file(); print(os.getenv('PROJECT_SETUP_OWNER_TYPE', ''))")

ifneq ($(origin TARGET),command line)
TARGET := $(ENV_TARGET)
endif
ifneq ($(origin REPO),command line)
REPO := $(ENV_REPO)
endif
ifneq ($(origin CONFIG),command line)
CONFIG := $(if $(strip $(ENV_CONFIG)),$(ENV_CONFIG),project_setup.json)
endif
ifneq ($(origin PROJECT_NUMBER),command line)
PROJECT_NUMBER := $(ENV_PROJECT_NUMBER)
endif
ifneq ($(origin OWNER_TYPE),command line)
OWNER_TYPE := $(ENV_OWNER_TYPE)
endif

PROFILE ?= core
PROJECT_TYPE ?=
OWNER ?=
FORCE ?= 0
LIVE ?= 0

# Make command-line OWNER_TYPE overrides the persistent .env value. Export it so
# every Python entrypoint sees the same Project v2 ownership decision.
export PROJECT_SETUP_OWNER_TYPE := $(OWNER_TYPE)

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
	@echo "Repository mode: $(REPOSITORY_MODE)"
	@echo ""
	@echo "Persistent defaults (.env):"
	@echo "  PROJECT_SETUP_TARGET=$(if $(strip $(TARGET)),$(TARGET),missing)"
	@echo "  GITHUB_REPOSITORY=$(if $(strip $(REPO)),$(REPO),missing)"
	@echo "  PROJECT_SETUP_OWNER_TYPE=$(if $(strip $(OWNER_TYPE)),$(OWNER_TYPE),auto-detect)"
	@echo "  PROJECT_SETUP_CONFIG=$(CONFIG)"
	@echo "  PROJECT_SETUP_PROJECT_NUMBER=$(if $(strip $(PROJECT_NUMBER)),$(PROJECT_NUMBER),not-set)"
	@echo ""
	@echo "First-time local setup:"
	@echo "  1. Copy .env.example to .env"
	@echo "  2. Set PROJECT_SETUP_TARGET and GITHUB_REPOSITORY"
	@echo "  3. Select PROJECT_SETUP_OWNER_TYPE=user or organization when using Project v2"
	@echo "  4. Add PROJECT_SETUP_PAT when Project v2 operations are needed"
	@echo "  5. Run make doctor"
	@echo "  6. Run make check"
	@echo ""
	@echo "Development:"
	@echo "  make install                         Install the CLI"
	@echo "  make dev-install                     Install in editable mode"
	@echo "  make check                           Validate managed files, compile and run the available test level"
	@echo "  make doctor                          Inspect OS, .env, gh auth and configuration"
	@echo "  make clean                           Remove local Python/build artifacts"
	@echo ""
	@echo "Repository analysis and setup (.env defaults):"
	@echo "  make discover                        Inspect the configured target"
	@echo "  make discover PROJECT_TYPE=python    Override detected project type"
	@echo "  make init-dry                        Preview copied automation files"
	@echo "  make init                            Copy core automation files"
	@echo "  make init FORCE=1                    Replace existing managed files"
	@echo "  make plan                            Preview configured GitHub changes"
	@echo "  make apply                           Dry-run by default"
	@echo "  make apply LIVE=1                    Apply changes"
	@echo "  make setup                           Init + remote dry-run"
	@echo "  make setup-live                      Init + live apply"
	@echo ""
	@echo "Project v2 owner selection:"
	@echo "  PROJECT_SETUP_OWNER_TYPE=user        Personal GitHub account"
	@echo "  PROJECT_SETUP_OWNER_TYPE=organization GitHub Organization/company"
	@echo "  make setup OWNER_TYPE=organization   One-off override"
	@echo "  Leave unset to auto-detect during authenticated Project v2 operations."
	@echo ""
	@echo "Individual operations (dry-run by default):"
	@echo "  make labels"
	@echo "  make milestones"
	@echo "  make issues"
	@echo "  make project-create"
	@echo "  make project-sync                    Uses PROJECT_SETUP_PROJECT_NUMBER"
	@echo "  make project-sync PROJECT_NUMBER=1   One-off project number override"
	@echo "  Add LIVE=1 only after reviewing the dry-run output."
	@echo ""
	@echo "One-off override example:"
	@echo "  make setup TARGET=../other-project REPO=owner/other-repository OWNER_TYPE=organization"

install:
	@echo "==> Installing project_setup"
	$(PIP) install .

dev-install:
	@echo "==> Installing project_setup in editable mode"
	$(PIP) install -e .

quality:
	@echo "==> [1/3] Validating repository structure and committed files ($(REPOSITORY_MODE))"
	$(PYTHON) scripts/validation/repo_quality.py

compile:
	@echo "==> [2/3] Compiling Python sources ($(REPOSITORY_MODE))"
	$(PYTHON) -m compileall -q $(COMPILE_PATHS)
	@$(MAKE) --no-print-directory clean-generated
	@echo "Python compilation passed. Generated cache files were removed."

test:
ifeq ($(TOOL_REPOSITORY),1)
	@echo "==> [3/3] Running tool repository unit tests"
	$(PYTHON) -B -m unittest discover -s tests -p "test_*.py" -v
else
	@echo "==> [3/3] Running embedded project_setup smoke test"
	$(PYTHON) -B -c "import project_setup; from project_setup.cli import build_parser; parser = build_parser(); assert parser.prog == 'project-setup'; print('Embedded project_setup smoke test passed.')"
endif

check: quality compile test
	@echo "All repository checks passed ($(REPOSITORY_MODE)). No GitHub API changes were made."

doctor:
	@echo "==> Inspecting local setup (read-only)"
	$(PYTHON) -m project_setup doctor --config "$(CONFIG)"

discover:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	$(PYTHON) -m project_setup discover --repo "$(REPO)" --config "$(CONFIG)" --root "$(TARGET)" $(PROJECT_TYPE_FLAG) --auto

init:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(PYTHON) -m project_setup init --target "$(TARGET)" --profile "$(PROFILE)" $(FORCE_FLAG) --live

init-dry:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(PYTHON) -m project_setup init --target "$(TARGET)" --profile "$(PROFILE)" $(FORCE_FLAG) --dry-run

plan:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup apply --repo "$(REPO)" --config "$(CONFIG)" --dry-run

apply:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup apply --repo "$(REPO)" --config "$(CONFIG)" $(EXECUTION_FLAG)

setup: init plan

setup-live:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	$(MAKE) --no-print-directory init TARGET="$(TARGET)" PROFILE="$(PROFILE)" FORCE="$(FORCE)"
	$(MAKE) --no-print-directory apply TARGET="$(TARGET)" REPO="$(REPO)" CONFIG="$(CONFIG)" LIVE=1 OWNER_TYPE="$(OWNER_TYPE)"

labels:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup labels sync --repo "$(REPO)" --file config/project/labels.json $(EXECUTION_FLAG)

milestones:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup milestones sync --repo "$(REPO)" --file config/project/milestones.json $(EXECUTION_FLAG)

issues:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup issues generate --repo "$(REPO)" --file config/stories/backlog-manifest.json $(EXECUTION_FLAG)

project-create:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project create --repo "$(REPO)" --file config/project/project-definition.json $(EXECUTION_FLAG)

project-sync:
	$(call require_value,TARGET,set PROJECT_SETUP_TARGET in .env or use TARGET=../my-project)
	$(call require_value,REPO,set GITHUB_REPOSITORY in .env or use REPO=owner/repository)
	$(call require_value,PROJECT_NUMBER,set PROJECT_SETUP_PROJECT_NUMBER in .env or use PROJECT_NUMBER=1)
	cd "$(WORKDIR)" && $(PYTHON) -m project_setup project sync --repo "$(REPO)" --project-number "$(PROJECT_NUMBER)" $(OWNER_FLAG) --file config/project/project-definition.json $(EXECUTION_FLAG)

clean-generated:
	@$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in list(Path('.').rglob('__pycache__'))]; [path.unlink(missing_ok=True) for pattern in ('*.pyc','*.pyo') for path in list(Path('.').rglob(pattern))]"

clean: clean-generated
	@$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(Path(name), ignore_errors=True) for name in ('build','dist','.pytest_cache','.mypy_cache')]; [shutil.rmtree(path, ignore_errors=True) for path in list(Path('.').glob('*.egg-info'))]"
	@echo "Local Python and build artifacts removed."
