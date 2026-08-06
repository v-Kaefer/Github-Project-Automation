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

```bash
python -m project_setup init --target ../target-repository
```

Existing files are preserved unless `--force` is explicitly selected. Existing Makefiles and environment templates should be reviewed and merged manually.

## Local environment

The CLI automatically loads `.env` from the current working directory without replacing variables that are already present in the process environment.

```bash
cp .env.example .env
make doctor
```

`make doctor` validates local files and credential availability without writing to GitHub.

## Configuration

`project_setup.json` controls the API phase and points to four manifests:

- labels;
- milestones;
- Project v2 definition;
- backlog stories and tasks.

Dry-run, Project creation and issue generation are independently configurable.

## Discovery

The `discover` command detects common Python, Node.js, Go, Java, Rust and .NET markers. It reports authentication status and prints the recommended `apply` command before any write operation.

## Profiles

- `core`: repository-neutral setup.
- `godot`: core plus the optional Godot smoke workflow stored under `templates/profiles/godot`.

Language- or framework-specific checks should be added as profiles instead of expanding the core workflow.

## Authentication boundary

Repository-scoped Actions operations use the standard token:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

No user-created `GITHUB_TOKEN` secret is needed. This token covers labels, milestones, issues, sub-issues, and PR comments within the repository, subject to the workflow `permissions` block.

GitHub Projects v2 are owned by a user or organization rather than a repository. Live Project creation or synchronization therefore requires `PROJECT_SETUP_PAT`.

For the current GraphQL implementation:

1. create a personal access token classic;
2. select `repo` and `project` scopes;
3. save it as `PROJECT_SETUP_PAT` in the local `.env`;
4. save the same credential as the `PROJECT_SETUP_PAT` Actions secret when manual workflows must operate on Projects v2.

The CLI and workflow fail before a live Project v2 operation if the explicit PAT is missing. They do not silently use `github.token` for that operation.

## Automation boundaries

The tool automates repository files, labels, milestones, issues, sub-issues and Project v2 fields/items. Branch protection, rulesets and Project views remain outside the automated core.
