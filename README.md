# GitHub Project Setup

A self-contained toolkit for installing and operating GitHub repository automation.

It detects common project stacks, copies reusable workflows and templates into another repository, validates the resulting setup, and synchronizes repository resources through the GitHub API. The tool is designed for direct use by developers and for assisted use by coding agents or other AI systems.

## Capabilities

- Detect Python, Node.js, Go, Java, Rust and .NET repository markers.
- Install issue forms, pull request templates and GitHub Actions workflows.
- Embed the `project_setup` Python package in the target repository.
- Synchronize labels and milestones from JSON manifests.
- Generate stories and implementation tasks from a backlog manifest.
- Create and populate GitHub Projects v2.
- Link generated tasks as sub-issues.
- Infer labels for issues and pull requests.
- Validate branch names and pull request metadata.
- Plan all supported changes in dry-run mode before writing to GitHub.

## Requirements

- Python 3.11 or newer.
- GNU Make for the Makefile interface. The Python CLI can be used directly on systems without Make.
- A GitHub token for live API operations.

Authentication lookup order:

1. `GITHUB_TOKEN`
2. `GH_TOKEN`
3. `PROJECT_SETUP_PAT`
4. `gh auth token`, when the GitHub CLI is installed and authenticated

For the installed GitHub Actions workflow, configure the repository secret `PROJECT_SETUP_PAT` when Project v2 or other user-scoped permissions are required. Repository-scoped operations can fall back to `github.token`.

## Quick start

Validate this tool repository:

```bash
make check
```

Inspect the target project and print the recommended setup command:

```bash
make discover TARGET=../my-project REPO=owner/my-project
```

Install the core profile and preview the GitHub changes:

```bash
make setup TARGET=../my-project REPO=owner/my-project
```

The `setup` target is intentionally safe: it copies missing files and runs the API phase in dry-run mode.

After reviewing and customizing the generated files, apply the changes:

```bash
export PROJECT_SETUP_PAT=github_pat_...
make apply TARGET=../my-project REPO=owner/my-project
```

To install the optional Godot smoke workflow:

```bash
make init TARGET=../my-game PROFILE=godot
```

Existing files are preserved. Explicit replacement requires:

```bash
make init TARGET=../my-project FORCE=1
```

## Files to customize in the target repository

Before a live apply, review at least:

- `project_setup.json`
- `config/project/labels.json`
- `config/project/milestones.json`
- `config/project/project-definition.json`
- `config/stories/backlog-manifest.json`
- `.github/workflows/main-source-branch.yml`
- `.github/pull_request_template.md`

The sample backlog uses `owner/repository` deliberately. Project creation and issue generation are disabled by default.

## Makefile interface

| Target | Purpose |
| --- | --- |
| `make help` | Show commands and required variables. |
| `make install` | Install the CLI in the active Python environment. |
| `make dev-install` | Install the CLI in editable mode. |
| `make check` | Compile Python, validate repository structure and run tests. |
| `make doctor` | Inspect token and configuration availability. |
| `make discover TARGET=... REPO=...` | Detect the target stack and print a recommended command. |
| `make init TARGET=...` | Copy the embedded setup into a target repository. |
| `make init-dry TARGET=...` | Preview copied files without writing. |
| `make plan REPO=...` | Preview GitHub API changes. |
| `make apply REPO=...` | Apply configured GitHub API changes. |
| `make setup TARGET=... REPO=...` | Install files and run a dry-run. |
| `make setup-live TARGET=... REPO=...` | Install files and perform a live apply. |

`TARGET` is optional for API-only targets. When provided, commands run from that repository so its local `project_setup.json` and manifests are used.

## Python CLI

The installed commands are equivalent:

```bash
project-setup --help
project_setup --help
python -m project_setup --help
```

Common operations:

```bash
python -m project_setup discover --repo owner/repository --root ../my-project --auto
python -m project_setup init --target ../my-project --profile core
python -m project_setup doctor --config project_setup.json
python -m project_setup apply --repo owner/repository --dry-run
python -m project_setup labels sync --repo owner/repository --dry-run
python -m project_setup project sync --repo owner/repository --project-number 1 --dry-run
```

## AI-assisted setup

An AI assistant should follow this order:

1. Inspect the target repository and identify its language, test framework, branch model and existing automation.
2. Run `discover` to verify the detected stack and proposed execution flags.
3. Run `init` without `--force`.
4. Replace the example repository, milestones, board fields and backlog entries with project-specific values.
5. Preserve existing project-specific workflows unless they are explicitly selected for replacement.
6. Run `make check` in this tool repository and compile the embedded package in the target repository.
7. Run `make plan TARGET=<path> REPO=<owner/repository>`.
8. Present the dry-run output for human review.
9. Perform a live apply only after explicit approval.

A suitable instruction for an agent is:

```text
Use the installed project_setup files as the automation baseline. Adapt the JSON manifests and workflows to this repository without deleting existing project-specific automation. Run discovery and dry-run validation first, and do not perform live GitHub writes until the proposed changes have been reviewed.
```

## Profiles

### `core`

Installs repository-neutral issue forms, pull request validation, auto-labeling, the Project setup workflow, manifests, validation scripts and the embedded Python package.

### `godot`

Installs everything in `core` and copies the optional Godot smoke workflow from `templates/profiles/godot`. Game tests, release exports and gameplay-specific checks are intentionally not part of the generic core.

## Safety model

- Dry-run is the default in `project_setup.json`.
- Issue generation is disabled by default.
- Project creation is disabled by default.
- Existing target files are skipped unless `--force` is explicitly provided.
- Pull request validation executes trusted code from the base commit.
- Workflow checkouts do not persist credentials.
- Concurrent runs for the same pull request are cancelled when superseded.

## Current limitations

- GitHub rulesets and branch protection are not created automatically yet.
- Project v2 views listed in the definition remain a manual configuration step.
- Issue generation is not idempotent; review existing issues before repeating it.
- The installer currently embeds the package in each target repository rather than depending on a published PyPI release.
- Repository-specific CI should be added as an optional profile instead of being placed in the core setup.

## Development

```bash
make dev-install
make check
```

The repository quality check rejects generated Python bytecode, invalid JSON/TOML and legacy package references.
