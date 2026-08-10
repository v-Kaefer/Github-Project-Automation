# PR Sync

## Status

**Implemented.**

PR Sync is the generic GitHub Project Setup automation that keeps an implementation pull request aligned with its linked issue/task and, when configured, GitHub Projects v2.

The implementation is composed of:

- `.github/workflows/pr-sync.yml` — trusted GitHub Actions orchestration;
- `project_setup/pr_sync.py` — synchronization logic;
- `project_setup.json` → `prAutomation.sync` — repository policy/configuration;
- `tests/test_pr_sync.py` — unit and workflow-contract coverage.

The feature is the generic successor to the repository-specific workflow previously called **PR Hygiene** in the Take Your Pills reference repository. New GPA code and documentation use **PR Sync**.

## Responsibility boundary

PR Sync does not replace PR Guardrails.

The intended pipeline is:

```text
Pull request event
      |
      v
PR Guardrails / current PR metadata validation
  - resolve or validate trusted PR context
  - validate branch/body contract
      |
      v
PR Sync
  - resolve linked implementation task
  - synchronize task -> PR metadata
  - synchronize parent/sub-issue relationship
  - synchronize task -> Project v2
  - synchronize PR lifecycle -> Project Status
```

The current GPA validation workflow is named `PR metadata validation`. PR Sync listens for successful completion of that workflow and also recognizes the reference-compatible `PR guardrails` workflow name so the orchestration remains valid when Guardrails is promoted to the generic name.

## Event model

Normal implementation updates run from `workflow_run` after the trusted PR validation/Guardrails workflow completes successfully.

Lifecycle events that do not need another validation pass run directly from `pull_request_target`:

- `converted_to_draft`;
- `closed`.

Both paths use automation from the trusted base branch. The workflow does not execute code from an untrusted PR head with write permissions.

Fork pull requests are skipped.

## Linked implementation task

PR Sync resolves the implementation issue/task from a closing reference in the PR body:

```text
Closes #123
Fixes #123
Resolves #123
```

If no closing reference exists, PR Sync writes or updates one marked status comment and returns a failure for the synchronization step.

If the referenced item is itself a pull request, it is rejected as an implementation task.

The closing reference is also the GitHub Development linkage between the PR and the issue/task; PR Sync builds its synchronization context from that canonical link rather than inventing another parallel association.

## Metadata synchronization

By default, the linked task is the source for these PR fields:

### Labels

Configured label families are copied to the PR when missing.

Default prefixes:

```text
type:
priority:
test:
```

PR Sync is additive: it does not remove unrelated or stale labels from the PR.

### Milestone

If the task has a milestone and the PR does not match it, the PR milestone is updated to the task milestone.

### Assignees

If task assignees exist, missing assignees are added to the PR.

If the task is unassigned and `assignAuthorWhenTaskUnassigned` is enabled, the PR author is assigned to the task and then synchronized to the PR.

These behaviors can be disabled independently in `project_setup.json`.

## Parent Story / sub-issue synchronization

Generated GPA task bodies already use a parent reference such as:

```text
Parent story: US-12 (#45)
```

When `linkSubissues` is enabled, PR Sync resolves that parent issue number and ensures the implementation task is linked as a GitHub sub-issue.

Repeated execution is idempotent for an already-existing parent/sub-issue relationship. Permission failures are reported as synchronization diagnostics instead of causing duplicate mutations.

## Project v2 synchronization

When all of the following are configured:

- `syncProject: true`;
- Actions variable `PROJECT_SETUP_PROJECT_NUMBER`;
- Actions secret `PROJECT_SETUP_PAT`;

PR Sync ensures that the linked task belongs to the configured Project v2 and updates the configured single-select status field.

The Project owner continues to use the existing GPA owner-resolution contract. `PROJECT_SETUP_OWNER_TYPE` may be provided as an Actions variable when explicit `user` or `organization` selection is required.

If the Project number or PAT is missing, repository-level PR/task synchronization still runs and the sticky comment explains why Project synchronization was skipped.

## Default lifecycle mapping

The committed default mapping is:

| Pull request state | Project status target |
| --- | --- |
| Draft / converted to draft | `In progress` |
| Ready for review / validated open PR | `In review` |
| Closed without merge | `In progress` |
| Merged | `Done` |

The field name and option names are configurable. GPA resolves the configured option by normalized name rather than hard-coding one repository-specific Project schema.

## Promotion pull requests

PR Sync is intended for implementation pull requests, not branch-promotion infrastructure.

The default excluded paths are:

```text
develop -> Q.A
Q.A -> main
```

Promotion PRs are skipped before task lookup or metadata mutation. Repositories with a different promotion model can replace `promotionPaths` or disable `skipPromotionPullRequests`.

## Committed configuration schema

`project_setup.json` contains the active PR Sync configuration:

```json
{
  "prAutomation": {
    "sync": {
      "enabled": true,
      "syncLabels": true,
      "labelPrefixes": ["type:", "priority:", "test:"],
      "syncMilestone": true,
      "syncAssignees": true,
      "assignAuthorWhenTaskUnassigned": true,
      "linkSubissues": true,
      "syncProject": true,
      "skipPromotionPullRequests": true,
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

This is now an implementation contract, not a design placeholder.

## Authentication and permissions

Repository-scoped synchronization uses `${{ github.token }}` with the workflow's minimum repository permissions.

Project v2 synchronization uses the existing explicit GPA boundary:

```text
PROJECT_SETUP_PAT
```

The PAT is never written to logs or comments.

The workflow requests only:

```yaml
permissions:
  contents: read
  issues: write
```

PR labels, assignees, milestone changes and PR comments are performed through GitHub's issue endpoints because pull requests are issue-backed resources.

## Security model

PR Sync follows the repository hardening introduced in the promotion-gate work:

- privileged PR automation is based on `pull_request_target` / trusted `workflow_run`;
- checkout points at the trusted base commit or trusted base branch;
- `persist-credentials` is disabled;
- fork PRs are rejected by both workflow conditions and implementation checks;
- no untrusted head code is executed with write permissions;
- GitHub mutation calls are not automatically replayed after transport failures;
- optional Project permission failures are surfaced clearly.

The same source/embedded-repository distinction documented in `project-setup-shared-tool.md` continues to apply when the workflow is distributed to target repositories.

## Idempotency

Repeated PR Sync execution is designed not to duplicate:

- labels already present on the PR;
- assignees already present on the PR;
- Project membership for an existing task;
- parent/sub-issue relationships already established;
- marked PR Sync comments.

Milestone and Project status updates converge toward the configured task/lifecycle state.

## Installation

`.github/workflows/pr-sync.yml` is part of the core installer manifest. Because package files under `project_setup/*.py` are distributed automatically, `project_setup/pr_sync.py` is installed with the workflow.

Existing target files remain protected by the installer's normal preserve-by-default behavior.

## Validation

`tests/test_pr_sync.py` covers the reusable contract, including:

- closing-reference parsing;
- generated parent-reference parsing;
- lifecycle status mapping;
- configuration overrides;
- label/milestone/assignee synchronization;
- author fallback for unassigned tasks;
- duplicate parent/sub-issue idempotency;
- fork safety;
- promotion-PR skip behavior;
- missing/invalid linked task behavior;
- sticky comment idempotency;
- trusted workflow checkout and dependency contract;
- installer distribution of the workflow.

Live Project v2 behavior remains a Q.A-sandbox concern. It must not use the source repository as the destructive integration-test target.

## Known limits

- PR Sync adds configured task labels but does not remove stale PR labels.
- It synchronizes assignees from task to PR; reviewer-request automation remains a Guardrails/review-policy responsibility rather than PR Sync.
- Project v2 synchronization is optional when its PAT/Project number are not configured.
- Promotion PR task synchronization is disabled by default.

## Naming

The generic feature and workflow name is **PR Sync**.

Do not introduce `PR Hygiene` in new GPA code, workflows, CLI/configuration names, or documentation except when referring historically to the Take Your Pills reference implementation.
