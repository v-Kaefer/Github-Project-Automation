# Documentation Guide

This guide maps the reusable configuration, workflows and operational documentation maintained by GitHub Project Setup.

## Config and documentation alignment

| Configuration | Purpose | Documentation |
| --- | --- | --- |
| `project_setup.json` | File paths and safe execution defaults | `docs/repo/project-setup-shared-tool.md`, `docs/repo/project-setup-runbook.pt-BR.md` |
| `config/project/labels.json` | Label names, colors and descriptions | `docs/repo/project-board-policy.md` |
| `config/project/milestones.json` | Milestone definitions | `docs/milestones/MILESTONE-TEMPLATE.md` |
| `config/project/project-definition.json` | Project v2 fields and options | `docs/repo/project-board-policy.md` |
| `config/stories/backlog-manifest.json` | Phases, stories and tasks | milestone and story documentation in the target repository |

## Operational guidance hierarchy

| Source | Authority |
| --- | --- |
| Target repository instructions and recorded conventions (`AGENTS.md`, `CONTRIBUTING*`, README/docs, existing workflows/configuration) | Authoritative for repository-specific decisions and established project standards. |
| `AI_SETUP_GUIDE.md` | Authoritative for the AI interaction sequence: inspect before asking, pause at checkpoints, re-verify user changes, protect credentials, and verify applied results. |
| `docs/repo/qa-policy.md` / `docs/repo/qa-policy.pt-BR.md` | Authoritative for the `develop -> Q.A -> main` promotion gates, compatibility matrix, sandbox requirements, and live/manual Q.A behavior. |
| `docs/repo/pr-sync.md` / `docs/repo/pr-sync.pt-BR.md` | Design contract for the planned PR Sync feature; not an implementation-status claim until the feature lands. |
| `docs/repo/project-setup-runbook.pt-BR.md` | Detailed human operational procedure and troubleshooting path. |
| `README.md` / `README.pt-BR.md` | Concise user-facing overview, setup, authentication, commands, and safety model. |

The AI guide does not override project-specific conventions. Its purpose is to make an assistant discover and respect those conventions before proposing or applying generic defaults.

## Workflows and sources

| Workflow | Purpose | Source of behavior |
| --- | --- | --- |
| `.github/workflows/project-setup.yml` | Manual dry-run or live setup | `project_setup/cli.py`, `project_setup/runner.py`, `project_setup.json` |
| `.github/workflows/auto-label.yml` | Infer labels for issues and PRs | `project_setup/auto_label.py` |
| `.github/workflows/pr-metadata.yml` | Validate branch names and PR metadata | `project_setup/pr_validation.py` |
| `.github/workflows/qa-source-branch.yml` | Allow promotion into `Q.A` only from `develop` | `docs/repo/branching-policy.md`, `project_setup/pr_validation.py` |
| `.github/workflows/qa-validation.yml` | Run deterministic cross-platform and package Q.A gates | `tests/qa/test_cli_e2e.py`, `tests/test_makefile_env_defaults.py`, `docs/repo/qa-policy.md` |
| `.github/workflows/qa-live.yml` | Run self-cleaning live integration tests in the protected `qa` Environment | `tests/qa/live_sandbox.py`, `docs/repo/qa-policy.md` |
| `.github/workflows/qa-issue-generation.yml` | Run guarded manual non-idempotent issue-generation validation | `tests/qa/live_issue_generation.py`, `docs/repo/qa-policy.md` |
| `.github/workflows/main-source-branch.yml` | Allow promotion into `main` only from `Q.A` | `docs/repo/branching-policy.md`, `project_setup/pr_validation.py` |
| `.github/workflows/repo-quality.yml` | Validate this tool repository | `Makefile`, `scripts/validation/repo_quality.py`, `tests/` |

## Feature design contracts

Feature branches may carry design documentation before implementation begins. These documents must say explicitly when behavior is planned rather than implemented.

Current design contracts:

- `docs/repo/pr-sync.md` / `docs/repo/pr-sync.pt-BR.md`: planned PR Sync orchestration, lifecycle mapping, security model, relationship to PR Guardrails, promotion-PR exclusions, and required regression/live validation.

When PR Sync is implemented, this guide must be updated in the same change to map the real workflow and source module rather than leaving it as a design-only contract.

## Adding a milestone template

1. Add the milestone to `config/project/milestones.json`.
2. Add its phase mapping and required options to `config/project/project-definition.json`.
3. Add stories under `phases` in `config/stories/backlog-manifest.json`.
4. Copy and complete `docs/milestones/MILESTONE-TEMPLATE.md` in the target repository when milestone documentation is useful.
5. Run a dry-run:

```bash
python -m project_setup apply --repo owner/repository --dry-run
```

6. Apply only after reviewing the proposed changes:

```bash
python -m project_setup apply --repo owner/repository --live
```

## Repository structure

```text
AI_SETUP_GUIDE.md                    Interaction contract for AI-guided configuration
project_setup/                       Reusable Python package
project_setup.json                   File paths and execution defaults
config/project/                      Labels, milestones and Project v2 definition
config/stories/                      Backlog manifest
.github/workflows/                   Generic active workflows and Q.A gates
docs/repo/                           Operational policies, runbooks, and feature design contracts
tests/qa/                            Q.A black-box, live sandbox, and guarded manual tests
scripts/validation/                  Cross-platform validation entrypoints
tests/                               Unit and installation tests
Makefile                             Human and AI-oriented command interface
```

When a configuration contract changes, update its loader, tests, README, AI guide when relevant, and the corresponding runbook or Q.A policy in the same pull request.
