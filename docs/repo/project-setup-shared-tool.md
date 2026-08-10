# Project Setup Shared Tool

## Package

The reusable engine is the Python package `project_setup`.

Entrypoints:

```bash
project-setup --help
project_setup --help
python -m project_setup --help
```

Feature-specific trusted workflows may also call a package module directly. PR Sync uses:

```bash
python -m project_setup.pr_sync --repo owner/repository --event-path "$GITHUB_EVENT_PATH"
```

## Distribution model

The installer embeds the package and managed automation files directly in the target repository. It also installs `Makefile` and `.env.example` when they do not already exist.

Preview installation:

```bash
python -m project_setup init --target ../target-repository --dry-run
```

Install files explicitly:

```bash
python -m project_setup init --target ../target-repository --live
```

Existing files are preserved unless `--force` is explicitly selected. Existing Makefiles and environment templates should be reviewed and merged manually. Installation dry-runs do not create the target directory.

All `project_setup/*.py` package modules are distributed automatically. Managed core workflows are listed explicitly by the installer; this now includes `.github/workflows/pr-sync.yml`.

## Source repository identity

The GPA development repository and an embedded target intentionally have different validation contracts.

The source repository is identified by the root marker:

```text
.project-setup-source
```

The marker must contain the exact source identity expected by repository-quality validation. It is source-only and is **not** part of the installer manifest.

This explicit marker replaces heuristic/path-based source detection. A target repository may legitimately contain a `Makefile`, tests, workflow files, or names that resemble GPA internals; those files alone must never switch the target into source-repository mode.

### Embedded target behavior

When the marker is absent, repository-quality validation treats the checkout as an embedded target:

- target-owned `Makefile` and workflow callers may be preserved;
- source-only caller/reference contracts are skipped where they are not applicable;
- managed scripts and installed automation remain validated;
- target files do not acquire source-repository obligations merely because their names resemble GPA files.

This boundary prevents the installer from making an external project accidentally responsible for the GPA source repository's internal wiring.

## Local environment

The CLI automatically loads `.env` from the current working directory without replacing variables that are already present in the process environment.

```bash
cp .env.example .env
make doctor
```

`make doctor` validates the operating system, Python executable, local files, token source, and GitHub CLI authentication without writing to GitHub.

## Configuration

`project_setup.json` points to the repository manifests and reusable automation policy.

Core manifest references include:

- labels;
- milestones;
- Project v2 definition;
- backlog stories and tasks.

`prAutomation.sync` configures PR Sync, including metadata families, assignee behavior, parent/sub-issue linking, Project status mapping, and promotion-PR exclusions.

Every normal mutating CLI command remains dry-run by default. The PR Sync module is different because it is an event-driven Actions worker: the workflow invokes it to converge already-validated PR metadata, while local testing can use `--dry-run`.

## Discovery

The `discover` command detects common Python, Node.js, Go, Java, Rust and .NET markers. It reports authentication status and prints a safely quoted recommended `apply` command before any write operation. Non-interactive discovery enforces dry-run in the recommended command.

## Authentication boundary

Repository-scoped Actions operations use the standard token:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

No user-created `GITHUB_TOKEN` secret is needed. This token covers labels, milestones, issues, sub-issues, and PR comments within the repository, subject to the workflow `permissions` block.

Local commands may also use `GITHUB_TOKEN`, `GH_TOKEN`, or a valid `gh auth` session. Diagnostics distinguish an unavailable CLI from an invalid CLI session and never print credentials.

GitHub Projects v2 are owned by a user or organization rather than a repository. Live Project creation or synchronization therefore requires `PROJECT_SETUP_PAT`.

For the current GraphQL implementation:

1. create a personal access token classic;
2. select `repo` and `project` scopes;
3. save it as `PROJECT_SETUP_PAT` in the local `.env`;
4. save the same credential as the `PROJECT_SETUP_PAT` Actions secret when workflows such as PR Sync must operate on Projects v2.

PR Sync also reads `PROJECT_SETUP_PROJECT_NUMBER` from an Actions variable. `PROJECT_SETUP_OWNER_TYPE` may be supplied as an Actions variable when owner auto-detection should be replaced by explicit `user` or `organization` selection.

If Project credentials/configuration are absent, PR Sync still performs repository-scoped task/PR synchronization and reports that Project synchronization was skipped.

## Request safety

GitHub API requests use a finite timeout. Automatic retries are limited to idempotent reads; mutation requests are not replayed after transport failures because a lost response could otherwise duplicate an issue or Project.

Privileged workflows that use `pull_request_target` must use trusted metadata and trusted base automation only. The promotion gates remain metadata-only and never check out PR code. PR Sync may check out automation, but only from the trusted base commit/branch with credentials persistence disabled.

## PR Sync boundary

PR Sync consumes a validated closing reference (`Closes/Fixes/Resolves #N`) and synchronizes:

- configured task labels to the PR;
- task milestone to the PR;
- task assignees to the PR;
- optional author assignment when the task is unassigned;
- generated parent Story relationship to GitHub sub-issue;
- linked task membership/status in Project v2;
- one marked status comment.

It skips forks and `develop -> Q.A` / `Q.A -> main` promotion PRs by default.

See [`pr-sync.md`](pr-sync.md).

## Automation boundaries

The tool automates repository files, labels, milestones, issues, sub-issues, PR synchronization, and Project v2 fields/items.

Branch protection, rulesets, Project views, and reviewer-selection policy remain outside PR Sync's automated core. Reviewer resolution belongs to PR Guardrails/review policy.
