# PR Sync

## Status

**Implemented.**

PR Sync is GPA's post-Guardrails synchronization lane. The public workflow is `.github/workflows/pr-sync.yml`; `project_setup.pr_sync_router` selects one of two modes:

```text
Implementation PR -> project_setup.pr_sync
Promotion PR      -> project_setup.promotion_sync
```

Normal synchronization runs only after successful Guardrails through `workflow_run`, and each path refetches live PR state instead of relying on an Autofill-mutated webhook payload.

## Pipeline

```text
PR event
  -> Autofill
  -> live Guardrails
  -> workflow_run on success
  -> PR Sync Router
       -> Implementation Sync
       -> Promotion Sync
```

Lifecycle events that need a direct transition also enter the router:

- `ready_for_review`;
- `converted_to_draft`;
- `closed`.

## Implementation Sync

Implementation PRs identify one canonical linked issue/task with:

```text
Closes #123
Fixes #123
Resolves #123
```

The task can drive:

- configured PR label families;
- PR milestone;
- PR assignees;
- parent/sub-issue linkage;
- task Project v2 membership/status.

When the task has no assignee and `assignAuthorWhenTaskUnassigned` is enabled, the PR author can be assigned to both the task and PR.

## Promotion Sync

Promotion paths are not skipped. They route to aggregate synchronization.

Committed paths:

```text
develop -> Q.A
Q.A -> main
```

The promotion's `## Related PRs` manifest is authoritative after Guardrails. Promotion Sync never selects the first linked issue as a fake canonical task.

It performs four responsibilities:

1. aggregate GitHub-native metadata from all constituent PRs;
2. apply that metadata to the promotion PR;
3. add/update the promotion PR itself in Project v2 when configured;
4. maintain stage-specific backlinks on constituent PRs.

### Native metadata aggregation

Configured managed label families use consensus. Defaults:

```text
type:
priority:
test:
```

If every related PR has the same single value for a family, the promotion receives that label. Missing/conflicting values result in no managed label for that family; the sticky Promotion Sync comment reports the conflict. Unmanaged labels already on the promotion are preserved.

Milestone also requires unanimous agreement. A conflict or missing milestone does not cause GPA to pick one arbitrarily.

Assignees are multi-valued and therefore use the deduplicated union of all related PR assignees.

### Promotion Project v2 membership

Implementation Sync keeps tasks as Project work items. Promotion Sync additionally adds the **promotion PR itself** to the configured Project so the promotion/release lifecycle can be represented and the PR's native `Projects` sidebar can show membership.

Default lifecycle:

| PR state | Project status |
| --- | --- |
| Draft | `In progress` |
| Open / review | `In review` |
| Closed without merge | `In progress` |
| Merged | `Done` |

Project operations require both `PROJECT_SETUP_PAT` and `PROJECT_SETUP_PROJECT_NUMBER`. Repository-scoped metadata still synchronizes if Project configuration is absent.

## Related PR Detection

`project_setup.related_prs` owns promotion discovery, Autofill, and validation.

The detector unions and deduplicates:

1. merged PRs whose head branch matches configured regexes;
2. explicit references in configured body sections;
3. references inherited from earlier promotion PRs.

Default patterns are broad examples:

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

Repositories may replace the entire list in `project_setup.json`.

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

The same `syncLabels`, `syncMilestone`, `syncAssignees`, and `syncProject` flags apply to implementation and promotion modes; promotion mode changes the aggregation semantics, not the configuration surface.

## Authentication and permissions

Repository-scoped synchronization uses `${{ github.token }}` with:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: write
```

`PROJECT_SETUP_PAT` is reserved for optional GitHub Projects v2 operations.

## Idempotency

Implementation Sync converges without duplicating labels, assignees, Project membership, parent relationships, or its marked status comment.

Promotion Sync:

- replaces only managed label families while preserving unmanaged labels;
- converges milestone to the aggregate consensus;
- adds missing assignees without duplicates;
- reuses existing Project membership when visible;
- updates lifecycle Status on the same Project item;
- updates stage-specific backlink/sticky comments rather than appending duplicates.

## Live validation

The protected `Q.A -> main` live lane validates three increasingly complete layers:

1. resource create/update/idempotency/cleanup;
2. Implementation PR Sync on a non-default base branch;
3. Promotion Sync with real merged constituent PRs.

The promotion smoke fails unless the **promotion PR object itself** has native labels, milestone, assignees, Project v2 membership/status, and correct merged lifecycle convergence. A successful sticky comment alone is not accepted as evidence.

See `pr-governance-architecture.md` for the Mermaid execution model.
