# Documentation Guide

This guide maps every documentation artifact in this repository to the config files and CLI commands that drive it.  
When you add or change a doc, update the corresponding config. When you change a config, update the corresponding doc.

---

## Config ↔ Doc alignment

| Config file | Purpose | Corresponding doc(s) |
|-------------|---------|----------------------|
| `config/project/milestones.json` | Milestone titles and due dates | `docs/milestones/MN-<slug>.md` (one per milestone) |
| `config/project/labels.json` | Label names, colors, descriptions | `docs/repo/project-board-policy.md` (status baseline) |
| `config/project/project-definition.json` | Board name, custom fields, views | `docs/repo/project-board-policy.md` |
| `config/stories/backlog-manifest.json` | Milestones → user stories → tasks | `docs/stories/story-index.md`, `docs/milestones/MN-<slug>.md` |
| `config/phases/phase-review-policy.json` | Review layers and responsible pairs per milestone | `docs/repo/review-policy.md` |
| `governance.bootstrap.json` | Entry point — file paths and default flags | `docs/repo/governance-shared-tool.md`, `docs/repo/governance-bootstrap-runbook.pt-BR.md` |

---

## Workflows ↔ Docs

| Workflow | What it does | Where to configure it |
|----------|--------------|-----------------------|
| `governance-bootstrap.yml` | Syncs labels, milestones, project board and issues | `governance.bootstrap.json` + `config/` |
| `auto-label.yml` | Infers and applies labels to issues and PRs | `governance_bootstrap/auto_label.py` |
| `pr-metadata.yml` | Validates PR body has required sections and an issue link | Inline bash check in the workflow |
| `branch-naming.yml` | Enforces branch naming convention | `docs/repo/branching-policy.md` |
| `main-source-branch.yml` | Ensures PRs to `main` come from `develop` | `docs/repo/branching-policy.md` |

---

## How to create documentation for a new milestone

1. **Define the milestone** in `config/project/milestones.json`:
   ```json
   {"title": "MN", "description": "Short description", "due_on": "YYYY-MM-DDT00:00:00Z"}
   ```

2. **Add the milestone's stories and tasks** in `config/stories/backlog-manifest.json`:
   ```json
   {
     "milestone": "MN",
     "stories": [
       {
         "storyId": "US-NN",
         "title": "US-NN | Story title",
         "labels": ["type:user-story", "priority:high", "test:automated"],
         "body": "As a ..., I want ... so that ...",
         "acceptanceCriteria": "- Criterion 1\n- Criterion 2",
         "testStrategy": "- automated",
         "dod": "- Implementation complete\n- Tests passing\n- Reviewed and merged",
         "tasks": ["T-NN.1 | Task title"]
       }
     ]
   }
   ```

3. **Copy the milestone template** to `docs/milestones/MN-<slug>.md`:
   ```bash
   cp docs/milestones/MILESTONE-TEMPLATE.md docs/milestones/MN-my-feature.md
   ```
   Fill in the objective, scope, stories table, risks and exit criteria.

4. **Update the story index** at `docs/stories/story-index.md`:
   ```markdown
   - Milestone MN: US-NN, US-NN+1, ...
   ```

5. **Assign responsible pairs** in `config/phases/phase-review-policy.json`:
   ```json
   "milestoneResponsiblePairs": {
     "MN": ["@username1", "@username2"]
   }
   ```

6. **Run the bootstrap** to apply labels, milestones and generate issues:
   ```bash
   python -m governance_bootstrap bootstrap --repo owner/repo --dry-run
   # review output, then:
   python -m governance_bootstrap bootstrap --repo owner/repo --no-dry-run
   ```

---

## Folder structure reference

```
docs/
  milestones/
    MILESTONE-TEMPLATE.md   # Copy this for each milestone
    MN-<slug>.md            # One per milestone (you create these)
  phases/
    README.md               # Guide for milestone docs (this folder is the old "phases" home)
  stories/
    README.md
    story-index.md          # All user stories grouped by milestone
  repo/
    branching-policy.md     # Branch naming and merge layer conventions
    review-policy.md        # PR review rules per merge layer
    dod-policy.md           # Definition of Done per item type and milestone
    project-board-policy.md # Required board fields and status values
    testing-policy.md       # Test type priority order and validation strategy
    handoff-policy.md       # What to register when ownership changes
    governance-shared-tool.md  # How to use this toolkit in another repo
    governance-bootstrap-runbook.pt-BR.md  # Step-by-step runbook
config/
  project/
    labels.json             # All labels — must match project-board-policy.md
    milestones.json         # Milestone titles and dates — must match docs/milestones/
    project-definition.json # Board fields — must match project-board-policy.md
  stories/
    backlog-manifest.json   # Milestones → stories → tasks — must match docs/milestones/
  phases/
    phase-review-policy.json  # Review layers and responsible pairs — must match review-policy.md
governance.bootstrap.json   # Entry point: file paths and CLI defaults
```
