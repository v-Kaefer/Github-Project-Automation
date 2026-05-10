# Shared Governance Tool

This repository carries the reusable bootstrap engine as the Python package `governance_bootstrap`.

## What Is Generic
- GitHub label sync from `config/project/labels.json`.
- GitHub milestone sync from `config/project/milestones.json`.
- GitHub Project v2 creation and issue sync from `config/project/project-definition.json`.
- Issue/task generation from `config/stories/backlog-manifest.json`.
- Auto-label and issue milestone helpers.
- `discover` wizard that checks auth, detects project type, and prints the recommended bootstrap command.

## What Stays Project-Specific
- Label names and colors.
- Milestone names and dates.
- Project board name, fields, options, views and `phaseMilestoneMap`.
- Backlog phases, user stories, tasks and default labels.
- The target repository passed with `--repo owner/repo`.

## Consumer Setup
1. Copy `governance.bootstrap.json`, `config/project`, `config/stories` and `.github/workflows/governance-bootstrap.yml` into the consumer repo.
2. Add a repository secret named `GOVERNANCE_PAT`.
3. Give the token access to `repo` issues and Project v2 operations (`project`, and `read:org` for orgs).
4. Run the manual workflow with `dry_run=true` to preview changes.
5. Run again with `dry_run=false` when the dry-run output looks correct.

## Local Usage

Check auth and get a recommended command interactively:

```bash
export GH_TOKEN=<your-PAT>
python -m governance_bootstrap discover --repo owner/repo --config governance.bootstrap.json
```

Run discovery in non-interactive (auto) mode:

```bash
python -m governance_bootstrap discover --repo owner/repo --config governance.bootstrap.json --auto
```

Run bootstrap directly (dry-run first):

```bash
python -m governance_bootstrap bootstrap --repo owner/repo --config governance.bootstrap.json --dry-run
# When output looks correct:
python -m governance_bootstrap bootstrap --repo owner/repo --config governance.bootstrap.json --no-dry-run
```

