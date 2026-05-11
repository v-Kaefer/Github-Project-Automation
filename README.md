# GitHub Project Automation

A reusable governance bootstrap toolkit for any GitHub project.  
It syncs labels, milestones, and a Project v2 board, generates issues/tasks from a backlog manifest, and auto-labels issues and PRs — all driven by JSON config files you drop into your repo.

---

## How it works

The toolkit has two parts:

| Part | What it is |
|---|---|
| `governance_bootstrap` | Generic Python CLI — never needs editing |
| `config/` + `governance.bootstrap.json` | Your project's data — edit these for every new project |

---

## Quick start

### 1. Copy config files into your repo

```
governance.bootstrap.json
config/project/labels.json
config/project/milestones.json
config/project/project-definition.json
config/stories/backlog-manifest.json
.github/workflows/governance-bootstrap.yml
.github/workflows/auto-label.yml
```

### 2. Edit the config files for your project

- **`labels.json`** — label names, colors, descriptions.
- **`milestones.json`** — milestone titles and due dates.
- **`project-definition.json`** — board name, custom fields, options and views.
- **`backlog-manifest.json`** — phases, user stories and tasks.
- **`governance.bootstrap.json`** — points to the above files; set `dryRun`, `runLabels`, etc.

### 3. Add a repository secret

Create a secret named `GOVERNANCE_PAT` with a PAT that has:
- `repo` (issues)
- `project` (Project v2)
- `read:org` (if the repo belongs to an org)

### 4. Run (GitHub Actions — recommended)

1. Go to **Actions → Governance bootstrap (manual) → Run workflow**.
2. Run with `dry_run = true` first to preview.
3. Run with `dry_run = false` to apply.

---

## Local CLI

Install the package:

```bash
pip install -e .
```

Guided wizard (checks auth, detects project type, shows recommended command):

```bash
export GH_TOKEN=<your-PAT>
python -m governance_bootstrap discover --repo owner/repo --config governance.bootstrap.json
```

Run directly:

```bash
# Dry-run (safe preview)
python -m governance_bootstrap bootstrap --repo owner/repo --dry-run

# Apply
python -m governance_bootstrap bootstrap --repo owner/repo --no-dry-run
```

Individual commands:

```bash
python -m governance_bootstrap labels sync --repo owner/repo
python -m governance_bootstrap milestones sync --repo owner/repo
python -m governance_bootstrap project create --repo owner/repo
python -m governance_bootstrap issues generate --repo owner/repo --link-subissues
python -m governance_bootstrap auto-label apply --repo owner/repo
```

---

## Repository layout

```
governance_bootstrap/   # Generic CLI tool (Python package)
config/
  project/
    labels.json             # Label definitions
    milestones.json         # Milestone list and dates
    project-definition.json # Project v2 board name, fields and views
  stories/
    backlog-manifest.json   # Phases, user stories and tasks
  phases/
    phase-review-policy.json
governance.bootstrap.json   # Bootstrap entry point (paths + defaults)
.github/workflows/
  governance-bootstrap.yml  # Manual dispatch workflow
  auto-label.yml            # Auto-labels issues and PRs on create/edit
  branch-naming.yml         # Validates branch name pattern
  main-source-branch.yml    # Ensures PRs to main come from develop
  pr-metadata.yml           # Validates required PR sections
```

---

## Authentication

The CLI reads the token from `GITHUB_TOKEN` or `GH_TOKEN`.  
If neither is set it falls back to `gh auth token` (if `gh` is installed).

