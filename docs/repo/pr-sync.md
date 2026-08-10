# PR Sync

## Status

This document defines the design contract for the planned **PR Sync** automation.

The `feat/pr-sync` branch was fast-forwarded to the current `main` baseline before this document was added. At this stage, the branch documents intended behavior only; PR Sync is not yet implemented.

PR Sync is the generic GitHub Project Setup successor to the repository-specific workflow previously called **PR Hygiene** in the Take Your Pills reference repository.

## Purpose

PR Sync keeps an implementation pull request and its linked GitHub work items aligned after PR Guardrails has resolved and validated the pull request context.

The intended execution order is:

```text
Pull request event
      |
      v
PR Guardrails
  - resolve context
  - autofill resolvable metadata
  - validate branch/body contract
      |
      v
PR Sync
  - synchronize linked task/issue metadata
  - synchronize parent/sub-issue relationship
  - synchronize Project v2 membership and status
```

PR Sync must not replace PR Guardrails. Guardrails establishes trusted context; PR Sync consumes that context and applies synchronization.

## Planned responsibilities

PR Sync is expected to support the following operations when enabled by repository configuration:

- resolve the implementation task from the PR closing reference (`Closes #N`, `Fixes #N`, or `Resolves #N`);
- copy configured label families from the linked task to the pull request;
- synchronize the pull request milestone with the linked task or resolved delivery context;
- synchronize assignees when repository policy enables it;
- ensure a task that declares a parent Story is linked as a GitHub sub-issue when possible;
- add the linked task to the configured GitHub Project v2 when it is not already present;
- synchronize the configured Project v2 status from the pull request lifecycle;
- maintain one marked/sticky PR Sync status comment rather than creating duplicate comments.

## Default lifecycle mapping

The generic default mapping should be configurable, but the initial contract is:

| Pull request state | Project status target |
| --- | --- |
| Draft / converted to draft | `In progress` |
| Ready for review / open validated PR | `In review` |
| Closed without merge | `In progress` |
| Merged | `Done` |

Repositories may use different option names. PR Sync must resolve configured aliases/options rather than hard-code a Take Your Pills-specific Project schema.

## Promotion pull requests

PR Sync is primarily intended for implementation pull requests. Promotion pull requests are infrastructure transitions:

```text
develop -> Q.A -> main
```

They must not be treated as implementation tasks by default. Unless a target repository explicitly enables release/promotion synchronization, PR Sync should skip task-level synchronization for these promotion paths.

This separation prevents a release promotion PR from accidentally inheriting labels, assignees, sub-issue relationships, or Project status intended for a single implementation task.

## Configuration direction

The exact configuration schema will be finalized during implementation. The intended shape is equivalent to:

```json
{
  "prAutomation": {
    "sync": {
      "enabled": true,
      "syncLabels": true,
      "syncMilestone": true,
      "syncAssignees": true,
      "linkSubissues": true,
      "syncProject": true,
      "skipPromotionPullRequests": true,
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

This is a design example, not yet a committed configuration schema.

## Authentication and permissions

Repository-scoped PR/issue synchronization should prefer the GitHub Actions token with the minimum required permissions. Project v2 operations may require `PROJECT_SETUP_PAT` depending on the repository owner, Project location, and token capabilities.

The workflow must never expose PAT values in logs or comments.

A failure to synchronize an optional surface such as Project v2 should produce a clear diagnostic and must not silently corrupt or overwrite unrelated PR metadata.

## Security model

The planned workflow should use trusted automation definitions (`pull_request_target` or a trusted follow-up workflow) only when it does not execute untrusted pull-request code.

PR Sync must:

- check out trusted base-branch automation when code checkout is required;
- avoid executing files from an untrusted PR head under elevated write permissions;
- use minimum GitHub token permissions;
- be idempotent for labels, milestone, assignees, Project membership, status, and sticky comments;
- handle `403`/permission failures as explicit synchronization diagnostics rather than masking the original validation result with an unrelated traceback.

## Relationship with existing GPA capabilities

GitHub Project Setup already contains reusable lower-level operations that PR Sync can compose, including:

- issue and PR label handling;
- milestone APIs;
- sub-issue linking support;
- Project v2 owner resolution;
- Project item creation and field synchronization;
- PR validation and marked validation comments.

The PR Sync feature should reuse these primitives instead of duplicating GitHub API implementations.

## Relationship with PR Guardrails

PR Guardrails is responsible for determining what can be inferred safely before validation. PR Sync should run only after that stage has successfully established the PR context.

A typical implementation PR should therefore become:

```text
feat/US-12-example
      |
      v
PR Guardrails
  Story / task / milestone resolution
  body autofill
  validation
      |
      v
PR Sync
  task -> PR labels/milestone/assignee
  Story <-> task relationship
  task -> Project v2
  PR lifecycle -> Project Status
```

## Validation requirements before promotion

Implementation of PR Sync must include automated coverage for at least:

- missing linked task;
- linked item is a pull request instead of an issue/task;
- existing versus missing labels;
- milestone synchronization;
- assignee synchronization and disabled-assignee mode;
- parent/sub-issue already linked versus missing;
- Project item already present versus missing;
- Project status transitions for draft, review, closed, and merged states;
- missing Project PAT or insufficient Project permission;
- promotion PR skip behavior;
- repeated execution without duplicate side effects;
- same-repository and fork safety boundaries.

Live Project v2 behavior should use the dedicated Q.A sandbox rather than the source repository.

## Naming

The generic feature and workflow name is **PR Sync**.

Do not use `PR Hygiene` in new GPA code, workflows, CLI commands, configuration, or documentation except when referring historically to the Take Your Pills implementation from which behavior was evaluated.
