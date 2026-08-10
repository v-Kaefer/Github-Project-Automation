# Documentation Guide

This guide maps the reusable configuration, workflows and operational documentation maintained by GitHub Project Setup.

## Config and documentation alignment

| Configuration | Purpose | Documentation |
| --- | --- | --- |
| `project_setup.json` | File paths, safe execution defaults, and `prAutomation.sync` policy | `docs/repo/project-setup-shared-tool.md`, `docs/repo/pr-sync.md`, `docs/repo/project-setup-runbook.pt-BR.md` |
| `config/project/labels.json` | Label names, colors and descriptions | `docs/repo/project-board-policy.md` |
| `config/project/milestones.json` | Milestone definitions | `docs/milestones/MILESTONE-TEMPLATE.md` |
| `config/project/project-definition.json` | Project v2 fields and options | `docs/repo/project-board-policy.md` |
| `config/stories/backlog-manifest.json` | Phases, stories and tasks | milestone and story documentation in the target repository |
| `.project-setup-source` | Explicit identity marker for the GPA source repository; never installed into targets | `docs/repo/project-setup-shared-tool.md`, `docs/repo/branching-policy.md` |

## Operational guidance hierarchy

| Source | Authority |
| --- | --- |
| Target repository instructions and recorded conventions (`AGENTS.md`, `CONTRIBUTING*`, README/docs, existing workflows/configuration) | Authoritative for repository-specific decisions and established project standards. |
| `AI_SETUP_GUIDE.md` | Authoritative for the AI interaction sequence: inspect before asking, pause at checkpoints, re-verify user changes, protect credentials, and verify applied results. |
| `docs/repo/qa-policy.md` / `docs/repo/qa-policy.pt-BR.md` | Authoritative for the `develop -> Q.A -> main` promotion gates, compatibility matrix, sandbox requirements, and live/manual Q.A behavior. |
| `docs/repo/pr-sync.md` / `docs/repo/pr-sync.pt-BR.md` | Authoritative implementation contract for PR Sync: inputs, synchronization behavior, security, Project mapping, configuration, and limits. |
| `docs/repo/branching-policy.md` / `docs/repo/branching-policy.pt-BR.md` | Branch topology plus trusted metadata-only promotion-gate security contract. |
| `docs/repo/project-setup-shared-tool.md` | Distribution model, source/embedded repository boundary, authentication boundary, and reusable automation internals. |
| `docs/repo/project-setup-runbook.pt-BR.md` | Detailed human operational procedure and troubleshooting path. |
| `README.md` / `README.pt-BR.md` | Concise user-facing overview, setup, authentication, commands, and safety model. |

The AI guide does not override project-specific conventions. Its purpose is to make an assistant discover and respect those conventions before proposing or applying generic defaults.

## Workflows and sources

| Workflow | Purpose | Source of behavior |
| --- | --- | --- |
| `.github/workflows/project-setup.yml` | Manual dry-run or live setup | `project_setup/cli.py`, `project_setup/runner.py`, `project_setup.json` |
| `.github/workflows/auto-label.yml` | Infer labels for issues and PRs | `project_setup/auto_label.py` |
| `.github/workflows/pr-metadata.yml` | Validate branch names and PR metadata; current Guardrails-stage workflow | `project_setup/pr_validation.py` |
| `.github/workflows/pr-sync.yml` | After successful Guardrails/metadata validation, synchronize linked task/PR/Project state; handle draft/closed lifecycle events | `project_setup/pr_sync.py`, `project_setup.json`, `tests/test_pr_sync.py`, `docs/repo/pr-sync.md` |
| `.github/workflows/qa-source-branch.yml` | Metadata-only trusted gate: allow promotion into `Q.A` only from `develop` | `docs/repo/branching-policy.md`, `tests/test_qa_workflows.py` |
| `.github/workflows/qa-validation.yml` | Run deterministic cross-platform and package Q.A gates | `tests/qa/test_cli_e2e.py`, `tests/test_makefile_env_defaults.py`, `docs/repo/qa-policy.md` |
| `.github/workflows/qa-live.yml` | Run self-cleaning live integration tests in the protected `qa` Environment | `tests/qa/live_sandbox.py`, `docs/repo/qa-policy.md` |
| `.github/workflows/qa-issue-generation.yml` | Run guarded manual non-idempotent issue-generation validation | `tests/qa/live_issue_generation.py`, `docs/repo/qa-policy.md` |
| `.github/workflows/main-source-branch.yml` | Metadata-only trusted gate: allow promotion into `main` only from `Q.A` | `docs/repo/branching-policy.md`, `tests/test_qa_workflows.py` |
| `.github/workflows/repo-quality.yml` | Validate this tool repository and distinguish source vs embedded target mode | `Makefile`, `scripts/validation/repo_quality.py`, `.project-setup-source`, `tests/` |

## PR automation pipeline

The reusable implementation path is:

```text
implementation PR
  |
  v
PR metadata validation / PR Guardrails
  |
  | successful trusted context
  v
PR Sync
  |
  +--> task labels / milestone / assignees -> PR
  +--> parent Story <-> sub-issue
  +--> task -> Project v2
  +--> PR lifecycle -> Project Status
```

Promotion PRs remain infrastructure transitions and are excluded from task-level PR Sync by default:

```text
develop -> Q.A -> main
```

## Source and embedded repository validation

Recent repository-mode hardening is part of the documented contract:

- `.project-setup-source` explicitly identifies the GPA source repository;
- promotion source gates use `pull_request_target` as metadata-only workflows and do not check out PR code;
- the source marker is not distributed into target repositories;
- embedded targets may keep their own Makefile/workflow callers without inheriting source-only caller contracts;
- managed target files are still validated for target-appropriate correctness.

This prevents a target project from being misdetected as GPA source merely because it contains similar paths or filenames.

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
.project-setup-source                Source-only GPA repository identity marker
project_setup/                       Reusable Python package, including PR Sync
project_setup.json                   File paths, execution defaults, PR automation policy
config/project/                      Labels, milestones and Project v2 definition
config/stories/                      Backlog manifest
.github/workflows/                   Generic active workflows, PR automation, Q.A gates
docs/repo/                           Operational policies, runbooks, implementation contracts
tests/qa/                            Q.A black-box, live sandbox, and guarded manual tests
scripts/validation/                  Cross-platform validation entrypoints
tests/                               Unit, installation and workflow-contract tests
Makefile                             Human and AI-oriented command interface
```

When a configuration or workflow contract changes, update its loader/implementation, tests, documentation guide, README or AI guide when user-facing behavior changes, and the corresponding policy/runbook in the same pull request.
