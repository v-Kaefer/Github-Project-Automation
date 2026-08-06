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

The installer embeds the package and managed automation files directly in the target repository. This makes Actions runs reproducible and avoids requiring a published package.

```bash
python -m project_setup init --target ../target-repository
```

Existing files are preserved unless `--force` is explicitly selected.

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

## Automation boundaries

The tool automates repository files, labels, milestones, issues, sub-issues and Project v2 fields/items. Branch protection, rulesets and Project views remain outside the automated core.

## Authentication

The CLI checks `GITHUB_TOKEN`, `GH_TOKEN`, `PROJECT_SETUP_PAT`, and finally an authenticated `gh` CLI session. The Actions workflow uses `PROJECT_SETUP_PAT` when configured and otherwise falls back to `github.token` for repository-scoped operations.
