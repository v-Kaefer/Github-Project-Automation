# Project Setup Shared Tool

## Package

The reusable engine is the Python package `project_setup`.

Entrypoints:

```bash
project-setup --help
project_setup --help
python -m project_setup --help
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

## Local environment

The CLI automatically loads `.env` from the current working directory without replacing variables that are already present in the process environment.

```bash
cp .env.example .env
make doctor
```

`make doctor` validates the operating system, Python executable, local files, token source, and GitHub CLI authentication without writing to GitHub.

## Configuration

`project_setup.json` points to four manifests and selects which API modules participate:

- labels;
- milestones;
- Project v2 definition;
- backlog stories and tasks.

Every mutating CLI command remains dry-run by default. A live operation requires `--live`, the compatible `--no-dry-run` alias, or `LIVE=1` through Make.

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
4. save the same credential as the `PROJECT_SETUP_PAT` Actions secret when manual workflows must operate on Projects v2.

The CLI and workflow fail before a live Project v2 operation if the explicit PAT is missing. They do not silently use `github.token` for that operation. A Project sync dry-run without the PAT falls back to an offline preview and clearly states that remote data was not queried.

## Request safety

GitHub API requests use a finite timeout. Automatic retries are limited to idempotent reads; mutation requests are not replayed after transport failures because a lost response could otherwise duplicate an issue or Project.

## Automation boundaries

The tool automates repository files, labels, milestones, issues, sub-issues and Project v2 fields/items. Branch protection, rulesets and Project views remain outside the automated core.
