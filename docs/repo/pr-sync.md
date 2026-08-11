# PR Sync

## Status

**Implemented.**

PR Sync is GPA's post-Guardrails synchronization lane. It now supports two distinct contexts:

- **Implementation Sync** — one canonical linked issue/task;
- **Promotion Sync** — an aggregate manifest of related pull requests.

The public workflow remains `.github/workflows/pr-sync.yml`, while `project_setup/pr_sync_router.py` chooses the correct synchronization mode.

## Pipeline

```text
PR event
  -> Autofill
  -> Guardrails
  -> workflow_run on success
  -> PR Sync Router
       -> Implementation Sync
       -> Promotion Sync
```

PR Sync never relies on an Autofill-mutated copy of the original webhook payload. Normal post-Guardrails execution refetches the live pull request.

## Implementation Sync

Implementation PRs use `project_setup/pr_sync.py`.

The linked issue/task is identified by a closing reference:

```text
Closes #123
Fixes #123
Resolves #123
```

The linked task can provide:

- configured label families;
- milestone;
- assignees;
- parent/sub-issue relationship;
- optional Project v2 membership/status.

If the task has no assignee and `assignAuthorWhenTaskUnassigned` is enabled, the PR author can be assigned to the task and synchronized to the PR.

### Default Project lifecycle

| Pull request state | Project status target |
| --- | --- |
| Draft / converted to draft | `In progress` |
| Ready for review / validated open PR | `In review` |
| Closed without merge | `In progress` |
| Merged | `Done` |

Project v2 operations remain optional and use `PROJECT_SETUP_PAT`. Ordinary PR/issue mutations use the built-in Actions token.

## Promotion Sync

Promotion paths are not skipped anymore at the workflow level. They route to aggregate Promotion Sync.

Committed paths:

```text
develop -> Q.A
Q.A -> main
```

Promotion Sync does **not** select an arbitrary first issue/task. It reads the promotion PR's `## Related PRs` manifest and maintains idempotent backlinks from those related PRs to the current promotion.

For example:

```text
feature/fix PRs -> develop
        |
        v
develop -> Q.A promotion
        |
        v
Promotion Sync backlinks related implementation PRs to Q.A
        |
        v
Q.A -> main promotion
        |
        v
Promotion Sync records the main-stage linkage
```

Related PR discovery and promotion-body Autofill happen before Guardrails in `project_setup.related_prs`; see `pr-governance-architecture.md`.

## Related PR Detection

The detector unions and deduplicates:

1. merged PRs whose head branch matches configured branch regexes;
2. PR references explicitly provided in configured body sections;
3. references inherited from earlier promotion PRs merged into the current promotion source branch.

Default branch patterns are deliberately broad configuration examples:

```text
^feat/
^fix/
^docs/
^refactor/
^test/
^hotfix/
^phase/
^task/
^chore/
^ci/
^release/
```

A repository can replace the entire list. Explicit body references remain valid even when a referenced PR does not match those patterns.

## Configuration

```json
{
  "prAutomation": {
    "relatedPrs": {
      "enabled": true,
      "branchPatterns": [
        "^feat/",
        "^fix/",
        "^docs/",
        "^refactor/",
        "^test/",
        "^hotfix/",
        "^phase/",
        "^task/",
        "^chore/",
        "^ci/",
        "^release/"
      ],
      "bodySections": ["Related PRs", "Related Pull Requests"],
      "includeBranchMatches": true,
      "includeBodyReferences": true,
      "inheritBodyReferences": true,
      "fallbackDays": 7
    },
    "sync": {
      "enabled": true,
      "syncLabels": true,
      "labelPrefixes": ["type:", "priority:", "test:"],
      "syncMilestone": true,
      "syncAssignees": true,
      "assignAuthorWhenTaskUnassigned": true,
      "linkSubissues": true,
      "syncProject": true,
      "promotionPaths": [
        {"head": "develop", "base": "Q.A"},
        {"head": "Q.A", "base": "main"}
      ],
      "projectStatusField": "Status",
      "projectStatus": {
        "draft": "In progress",
        "review": "In review",
        "closed": "In progress",
        "merged": "Done"
      }
    }
  }
}
```

`promotionPaths` are routing rules. The committed configuration no longer exposes `skipPromotionPullRequests`.

## Event model

Normal synchronization runs from `workflow_run` after `PR metadata validation` succeeds.

Lifecycle events that need a direct transition also enter the router through `pull_request_target`:

- `ready_for_review`;
- `converted_to_draft`;
- `closed`.

Both paths execute trusted base-branch automation. Fork PRs are excluded from privileged mutations.

## Authentication and permissions

Repository-scoped synchronization uses `${{ github.token }}` with:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: write
```

`PROJECT_SETUP_PAT` is reserved for optional GitHub Projects v2 operations. Promotion detection, promotion Autofill, promotion validation, and promotion backlinks require only repository-scoped permissions.

## Idempotency

Implementation Sync converges without duplicating labels, assignees, Project membership, parent/sub-issue links, or its marked status comment.

Promotion Sync uses stage-specific marked backlink comments so repeated runs update existing promotion linkage instead of adding duplicates.

## Security model

- trusted base/default-branch automation only;
- no untrusted head code runs with write credentials;
- `persist-credentials: false` on privileged checkouts;
- Guardrails success is required before normal synchronization;
- live PR state is refetched between state-changing and state-consuming stages;
- related PR references are validated as real merged PRs before promotion;
- Project v2 credentials stay isolated from ordinary repository mutations.

## Installation

The installer distributes `.github/workflows/pr-sync.yml`, while Python modules under `project_setup/*.py` include:

```text
pr_sync.py
pr_sync_router.py
related_prs.py
```

Existing target files remain subject to the installer's preserve-by-default behavior.

## Validation

Coverage is split between:

- `tests/test_pr_sync.py` — implementation synchronization and workflow safety;
- `tests/test_pr_sync_autofill.py` — implementation Autofill ordering;
- `tests/test_related_prs.py` — branch/body related-PR detection, configurable patterns, promotion-body aggregation, and router dispatch.

Live Project v2 and Q.A integration behavior remain sandbox concerns rather than destructive source-repository tests.
