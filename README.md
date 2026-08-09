[![Repository quality](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml/badge.svg?branch=develop)](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/v-Kaefer/Github-Project-Automation)
[![Agent Ready](https://img.shields.io/badge/Agent-Ready-6f42c1.svg)](AI_SETUP_GUIDE.md)

# GitHub Project Setup

[Português (Brasil)](README.pt-BR.md) · [AI-assisted setup](AI_SETUP_GUIDE.md) · [Quick start](#2-quick-start) · [Documentation](#6-documentation)

`project_setup` is a self-contained toolkit for installing and operating reusable GitHub repository automation. It combines a Makefile, a Python CLI, GitHub Actions workflows, manifests, and validation scripts so repositories can be configured manually, through automation, or with AI assistance without hiding what will be changed.

The project focuses on safe setup of labels, milestones, issues, sub-issues, pull-request guardrails, repository discovery, and GitHub Projects v2. Remote mutating commands default to dry-run and require an explicit live mode before writing to GitHub.

If an AI assistant will perform or guide the setup, give it [`AI_SETUP_GUIDE.md`](AI_SETUP_GUIDE.md). That file tells the agent to inspect existing repository conventions before asking questions, pause at manual/credential/live checkpoints, re-verify user changes before continuing, and avoid duplicate resources.

## 1. Overview

GitHub Project Setup is designed to be copied into a target repository and then operated from that repository. The installed package remains readable and editable instead of depending on an opaque remote service.

Typical uses include:

- bootstrap reusable GitHub workflows and issue/PR templates;
- synchronize labels and milestones from versioned JSON manifests;
- generate structured stories and tasks;
- optionally link generated tasks as sub-issues;
- create and synchronize GitHub Projects v2 owned by a personal account or GitHub Organization;
- validate pull-request metadata and repository conventions;
- inspect a repository and recommend a setup flow before applying it;
- expose the same operations to humans, scripts, and AI agents through predictable Make/CLI commands.

Safety is part of the interface: existing target files are preserved by default, API mutations are not automatically replayed after transport failures, credentials are not logged, and live execution must be requested explicitly.

## 2. Quick start

### Requirements

- Python 3.11+;
- Git;
- GNU Make for the Makefile interface;
- permission to access the target repository;
- `PROJECT_SETUP_PAT` only when live GitHub Projects v2 operations are required.

The Makefile detects Windows through `OS=Windows_NT`: it defaults to `python` on Windows and `python3` on POSIX environments. You can override the executable, for example:

```powershell
make PYTHON=py check
```

### Prepare the environment

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux, macOS, Git Bash, or WSL:

```bash
cp .env.example .env
```

Configure the target once:

```dotenv
PROJECT_SETUP_TARGET=../my-project
GITHUB_REPOSITORY=owner/my-project
PROJECT_SETUP_OWNER_TYPE=user
PROJECT_SETUP_CONFIG=project_setup.json
PROJECT_SETUP_PROJECT_NUMBER=
```

`PROJECT_SETUP_TARGET` is the local filesystem path. `GITHUB_REPOSITORY` is the GitHub `owner/repository` identifier. `PROJECT_SETUP_OWNER_TYPE` selects who owns GitHub Projects v2: use `user` for a personal account or `organization` for a company/team GitHub Organization. It may be left empty for authenticated auto-detection. Once a Project v2 exists, `PROJECT_SETUP_PROJECT_NUMBER` can store its number for `make project-sync`.

If the tool is already embedded in and operated from the target repository itself, use:

```dotenv
PROJECT_SETUP_TARGET=.
```

The Makefile resolves these values through the same `.env` parser used by the Python CLI. You normally configure them once instead of repeating `TARGET=` and `REPO=` on every command.

### Validate before setup

```bash
make doctor
make check
```

`make doctor` is read-only and reports the local environment, `.env`, token source, `gh auth` state, and referenced configuration files. `make check` validates repository structure, compiles the Python sources, and runs the test suite without writing to GitHub.

### Inspect and install

With `.env` configured, the normal flow becomes:

```bash
make discover
make init-dry
make setup
```

- `discover` inspects the configured local target and recommends a safe setup.
- `init-dry` previews the files that would be installed without creating the target directory.
- `setup` installs missing local automation files and then runs the configured GitHub phase in dry-run mode. It does **not** apply remote GitHub changes.

After reviewing the output, a complete live run is explicit:

```bash
make setup-live
```

Persistent configuration is only a convenience. A one-off override still works and has precedence over `.env`:

```bash
make setup TARGET=../other-project REPO=owner/other-project OWNER_TYPE=organization
```

`OWNER_TYPE=user|organization` overrides only the Project v2 owner type for that invocation. `LIVE=1` and `FORCE=1` intentionally remain command-line decisions rather than persistent `.env` defaults.

## 3. Authentication

| Use | Credential | Setup |
| --- | --- | --- |
| Repository operations inside GitHub Actions | `${{ github.token }}` exposed as `GITHUB_TOKEN` | [Automatic — no custom secret](#automatic-repository-token) |
| Local labels, milestones, issues, comments, and similar repository operations | valid `gh auth`, `GITHUB_TOKEN`, `GH_TOKEN`, or `PROJECT_SETUP_PAT` | [Manual/configured](#local-authentication) |
| Local GitHub Projects v2 | `PROJECT_SETUP_PAT` in `.env` | [Manual/configured PAT](#projects-v2-authentication) |
| GitHub Projects v2 from Actions | repository secret `PROJECT_SETUP_PAT` | [Manual/configured PAT + secret](#projects-v2-authentication) |

### Automatic repository token

GitHub creates `github.token` for each Actions job. Repository-scoped workflows use it through:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

Do not create a custom `GITHUB_TOKEN` secret for normal repository workflows. Effective access is controlled by each workflow's `permissions:` block.

### Local authentication

A local run can use an authenticated GitHub CLI session:

```bash
gh auth login
gh auth status
```

or a supported token in the environment file. `make doctor` reports which source is available and separately reports an invalid `gh auth` session without printing credentials. A broken `gh` session does not block execution when another valid token is configured.

### Projects v2 authentication

Live Project v2 creation/synchronization requires an explicit `PROJECT_SETUP_PAT`; the repository-scoped Actions token is not used as a silent fallback.

For the current GraphQL implementation, create a **personal access token (classic)**:

1. GitHub profile picture → **Settings**;
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**;
3. **Generate new token (classic)**;
4. choose an expiration and select `repo` and `project` scopes;
5. generate and copy the token.

For local execution:

```dotenv
PROJECT_SETUP_PAT=ghp_your_token_here
```

For Actions: repository **Settings** → **Secrets and variables** → **Actions** → **New repository secret** → `PROJECT_SETUP_PAT`.

Project owner type is independent from authentication. Configure `PROJECT_SETUP_OWNER_TYPE=user` or `PROJECT_SETUP_OWNER_TYPE=organization`, or leave it empty for auto-detection. See [Project v2 owner type](docs/repo/project-owner-type.md).

Never commit `.env`. See GitHub's documentation for [personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) and [Projects automation](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions).

## 4. Common commands

The target path and repository are normally read from `.env`. Remote mutating operations remain dry-run by default. Add `LIVE=1` only after reviewing the preview.

| Command | Default mode | What it does |
| --- | --- | --- |
| `make help` | Read-only | Shows detected platform, resolved `.env` defaults, Project owner type, Python command, and available targets. |
| `make doctor` | Read-only | Checks `.env`, token sources, `gh auth`, OS/Python, configuration, and referenced manifests. |
| `make check` | Local validation | Runs repository quality checks, compilation, and unit tests. |
| `make discover` | Read-only | Detects the configured target stack and prints a safe recommended setup command. |
| `make init-dry` | Dry-run | Shows which local automation files would be installed without creating the target directory. |
| `make init` | Local write | Installs missing managed files while preserving existing files. |
| `make setup` | Local install + remote dry-run | Installs missing files, then previews the configured API phase. |
| `make plan` | Dry-run | Previews the complete configured GitHub API phase. |
| `make apply` | Dry-run | Runs the configured API phase without writes. Add `LIVE=1` to apply. |
| `make labels` | Dry-run | Previews label synchronization. |
| `make milestones` | Dry-run | Previews milestone synchronization. |
| `make issues` | Dry-run | Previews story/task generation. |
| `make project-create` | Dry-run | Previews Project v2 creation using the configured/auto-detected owner type. |
| `make project-sync` | Dry-run | Uses `PROJECT_SETUP_PROJECT_NUMBER`; without a PAT it can show the offline Project definition preview. |
| `make clean` | Local write | Removes generated Python/build artifacts only. |

Examples of explicit writes:

```bash
make labels LIVE=1
make issues LIVE=1
make project-create LIVE=1
make apply LIVE=1
```

If a Project number is not stored yet:

```bash
make project-sync PROJECT_NUMBER=1
```

Any persistent target/repository value can be overridden for one invocation:

```bash
make plan TARGET=../other-project REPO=owner/other-project
make project-create OWNER_TYPE=organization
```

The equivalent CLI uses `--live`; `--no-dry-run` remains only as a compatibility alias.

## 5. Safety and execution model

The tool is intentionally conservative because repository setup mixes local files, GitHub REST resources, GraphQL resources, credentials, and potentially destructive writes.

- **Dry-run first:** every remote mutating CLI command previews by default. A live write requires `--live` or `LIVE=1`.
- **Persistent location, explicit mutation:** target/repository identity and Project owner type may live in `.env`, but `LIVE=1` and `FORCE=1` are deliberately not persistent defaults.
- **Preserve target files:** the installer skips existing files unless overwrite is explicitly requested. Existing Makefiles, environment templates, and AI instructions should be reviewed and merged rather than blindly replaced.
- **No filesystem side effect during install preview:** `init --dry-run` does not create the target directory.
- **Explicit Project v2 boundary:** live Project v2 operations require `PROJECT_SETUP_PAT`; they do not silently fall back to `github.token`.
- **Project owner namespace safety:** Project v2 operations query only the resolved `user` or `organization` GraphQL namespace instead of querying both for one login.
- **No credential logging:** diagnostics show credential source/status, never token values.
- **Safe HTTP behavior:** GitHub requests have a finite timeout and are restricted to `https://api.github.com`.
- **Mutation retry protection:** automatic transport retries are limited to idempotent reads. A lost response after a `POST`, `PATCH`, or `DELETE` is not automatically replayed.
- **Trusted privileged workflows:** workflows using `pull_request_target` execute automation from the trusted base branch. Read-only test workflows may validate proposed PR content.
- **Cross-platform entry points:** `.env` is parsed by Python rather than directly included by Make, keeping quoting and Windows behavior aligned with the CLI.

Current intentional limits: generated issues are not idempotent yet, Project v2 views remain manual, rulesets/branch protection are not created, and milestone synchronization inspects at most the first 100 existing milestones.

## 6. Documentation

| Document | What it contains |
| --- | --- |
| [AI setup guide](AI_SETUP_GUIDE.md) | Operational contract for AI assistants: inspect existing patterns first, ask only for unresolved decisions, pause for manual/credential/live checkpoints, re-verify user changes, and verify results after application. |
| [Portuguese README](README.pt-BR.md) | Complete Portuguese version of this overview, quick start, authentication, commands, safety model, environment defaults, and licensing information. |
| [Project owner type](docs/repo/project-owner-type.md) | How to select `user` versus `organization`, auto-detection behavior, Make overrides, GraphQL namespace handling, and Q.A coverage. |
| [Project Setup runbook (pt-BR)](docs/repo/project-setup-runbook.pt-BR.md) | Operational step-by-step procedure for configuring `.env`, diagnosing the environment, previewing, installing, and applying the tool in a target repository. |
| [Shared tool internals](docs/repo/project-setup-shared-tool.md) | Distribution model, package/CLI boundaries, authentication boundary, request-safety decisions, and what the reusable core automates. |
| [Branching policy](docs/repo/branching-policy.md) | Supported branch naming/source rules and the repository policy enforced around pull requests. |
| [Project board policy](docs/repo/project-board-policy.md) | Expected Project v2 fields, statuses, item types, and conventions used by the generic manifests. |
| [Script reference contract](docs/repo/script-reference-contract.md) | Contract that prevents validation scripts from becoming orphaned: each script must have an explicit caller and installer reference. |
| [Documentation guide](docs/DOCUMENTATION-GUIDE.md) | Map connecting configuration files, workflows, implementation files, and their authoritative documentation. |
| [Real test report](TESTE_REAL_RELATORIO.md) | Record of the first live end-to-end validation, including Project/issue creation and the environment problems discovered during that test. |

## 7. License and attribution

GitHub Project Setup is licensed under the [Apache License 2.0](LICENSE).

**Created and originally developed by [v-Kaefer](https://github.com/v-Kaefer).** The repository includes a [`NOTICE`](NOTICE) file carrying the project's attribution notice. Apache-2.0 requires distributed derivative works that include the relevant code to preserve applicable attribution notices from that NOTICE in a readable form.

When `project_setup` is embedded into another repository by the installer, its license and attribution files are installed under `licenses/project_setup/` so the target repository can retain its own top-level licensing model while still preserving this project's notices.