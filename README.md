[![Repository quality](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml/badge.svg?branch=develop)](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/v-Kaefer/Github-Project-Automation)

# GitHub Project Setup

[Português (Brasil)](README.pt-BR.md) · [Quick start](#2-quick-start) · [Documentation](#6-documentation)

`project_setup` is a self-contained toolkit for installing and operating reusable GitHub repository automation. It combines a Makefile, a Python CLI, GitHub Actions workflows, manifests, and validation scripts so a repository can be configured manually, through automation, or with AI assistance without hiding what will be changed.

The project focuses on safe setup of labels, milestones, issues, sub-issues, pull-request guardrails, repository discovery, and GitHub Projects v2. Mutating commands default to dry-run and require an explicit live mode before writing to GitHub.

## 1. Overview

GitHub Project Setup is designed to be copied into a target repository and then operated from that repository. The installed package remains readable and editable instead of depending on an opaque remote service.

Typical uses include:

- bootstrap reusable GitHub workflows and issue/PR templates;
- synchronize labels and milestones from versioned JSON manifests;
- generate structured stories and tasks;
- optionally link generated tasks as sub-issues;
- create and synchronize GitHub Projects v2;
- validate pull-request metadata and repository conventions;
- inspect a repository and recommend a setup flow before applying it;
- expose the same operations to humans, scripts, and AI agents through predictable Make/CLI commands.

Safety is part of the interface: existing target files are preserved by default, API mutations are not automatically replayed after transport failures, and live execution must be requested explicitly.

## 2. Quick start

### Requirements

- Python 3.11+;
- Git;
- GNU Make for the Makefile interface;
- permission to access the target repository;
- `PROJECT_SETUP_PAT` only when live GitHub Projects v2 operations are required.

The Makefile detects Windows through `OS=Windows_NT`: it defaults to `python` on Windows and `python3` on POSIX environments. You can override the executable, for example `make PYTHON=py check`.

### Validate this tool

```bash
make doctor
make check
```

`make doctor` is read-only and reports the local environment, `.env`, token source, `gh auth` state, and referenced configuration files. `make check` validates repository structure, compiles the Python sources, and runs the test suite without writing to GitHub.

### Prepare local configuration

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux, macOS, Git Bash, or WSL:

```bash
cp .env.example .env
```

At minimum, set the repository when you do not want to pass `REPO=` every time:

```dotenv
GITHUB_REPOSITORY=owner/repository
```

For Projects v2, also configure the PAT described in [Authentication](#3-authentication).

### Inspect and install into a target repository

```bash
make discover TARGET=../my-project REPO=owner/my-project
make init-dry TARGET=../my-project
make setup TARGET=../my-project REPO=owner/my-project
```

`init-dry` previews the files that would be installed. `setup` installs missing local automation files and then runs the configured GitHub phase in dry-run mode; it does **not** apply remote GitHub changes.

After reviewing the output, a complete live run is explicit:

```bash
make setup-live TARGET=../my-project REPO=owner/my-project
```

For finer control, use the individual commands in [Common commands](#4-common-commands).

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

Do not create a custom `GITHUB_TOKEN` secret for the normal repository workflows. Effective access is controlled by each workflow's `permissions:` block.

### Local authentication

A local run can use an authenticated GitHub CLI session:

```bash
gh auth login
gh auth status
```

or a supported token in the process/environment file. `make doctor` reports which source is available and separately reports an invalid `gh auth` session without printing credentials. A broken `gh` session does not block execution when another valid token is configured.

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

Never commit `.env`. See GitHub's documentation for [personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) and [Projects automation](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions).

## 4. Common commands

Dry-run is the default for remote mutating operations. Add `LIVE=1` only after reviewing the preview.

| Command | Default mode | What it does |
| --- | --- | --- |
| `make help` | Read-only | Shows detected platform, Python command, and available targets. |
| `make doctor` | Read-only | Checks `.env`, token sources, `gh auth`, OS/Python, configuration, and referenced manifests. |
| `make check` | Local validation | Runs repository quality checks, compilation, and unit tests. |
| `make discover TARGET=... REPO=...` | Read-only | Detects the target stack and prints a safe recommended setup command. |
| `make init-dry TARGET=...` | Dry-run | Shows which local automation files would be installed without creating the target directory. |
| `make init TARGET=...` | Local write | Installs missing managed files while preserving existing files. |
| `make setup TARGET=... REPO=...` | Local install + remote dry-run | Installs missing files, then previews the configured API phase. |
| `make plan TARGET=... REPO=...` | Dry-run | Previews the complete configured GitHub API phase. |
| `make apply TARGET=... REPO=...` | Dry-run | Runs the configured API phase without writes. Add `LIVE=1` to apply. |
| `make labels REPO=...` | Dry-run | Previews label synchronization. |
| `make milestones REPO=...` | Dry-run | Previews milestone synchronization. |
| `make issues REPO=...` | Dry-run | Previews story/task generation. |
| `make project-create REPO=...` | Dry-run | Previews Project v2 creation. |
| `make project-sync REPO=... PROJECT_NUMBER=1` | Dry-run | Previews Project v2 synchronization; without a PAT it falls back to an offline definition preview. |
| `make clean` | Local write | Removes generated Python/build artifacts only. |

Examples of explicit writes:

```bash
make labels REPO=owner/repository LIVE=1
make issues REPO=owner/repository LIVE=1
make project-create REPO=owner/repository LIVE=1
make apply TARGET=../my-project REPO=owner/repository LIVE=1
```

The equivalent CLI uses `--live`; `--no-dry-run` remains only as a compatibility alias.

## 5. Safety and execution model

The tool is intentionally conservative because repository setup mixes local files, GitHub REST resources, GraphQL resources, and credentials.

- **Dry-run first:** every remote mutating CLI command previews by default. A live write requires `--live` or `LIVE=1`.
- **Preserve target files:** the installer skips existing files unless overwrite is explicitly requested. Existing Makefiles and environment templates should be reviewed and merged rather than blindly replaced.
- **No filesystem side effect during install preview:** `init --dry-run` does not create the target directory.
- **Explicit Project v2 boundary:** live Project v2 operations require `PROJECT_SETUP_PAT`; they do not silently fall back to `github.token`.
- **No credential logging:** diagnostics show credential source/status, never token values.
- **Safe HTTP behavior:** GitHub requests have a finite timeout and are restricted to `https://api.github.com`.
- **Mutation retry protection:** automatic transport retries are limited to idempotent reads. A lost response after a `POST`, `PATCH`, or `DELETE` is not automatically replayed.
- **Trusted privileged workflows:** workflows using `pull_request_target` execute automation from the trusted base branch. Read-only test workflows may validate proposed PR content.
- **Cross-platform entry points:** platform-specific behavior is kept behind Python/Make interfaces so Windows does not depend on Unix-only `test` commands.

Current intentional limits: generated issues are not idempotent yet, Project v2 views remain manual, rulesets/branch protection are not created, and milestone synchronization inspects at most the first 100 existing milestones.

## 6. Documentation

| Document | What it contains |
| --- | --- |
| [Portuguese README](README.pt-BR.md) | Complete Portuguese version of this overview, quick start, authentication, commands, safety model, and licensing information. |
| [Project Setup runbook (pt-BR)](docs/repo/project-setup-runbook.pt-BR.md) | Operational step-by-step procedure for configuring, diagnosing, previewing, installing, and applying the tool in a target repository. |
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
