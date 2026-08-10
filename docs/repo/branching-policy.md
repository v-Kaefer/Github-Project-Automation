# Branching Policy (EN)

## Default branches

- `main`: stable delivery branch.
- `Q.A`: release-candidate and validation branch.
- `develop`: integration branch.
- `phase/<phase-name>`: optional phase branch for staged delivery.
- implementation branches: `feat/`, `fix/`, `task/`, `docs/`, `refactor/`, `test/`, `chore/`, `ci/`, `hotfix/`, or `release/`.

## Default merge layers

1. implementation branch -> `develop` or a phase branch;
2. phase branch -> `develop`;
3. `develop` -> `Q.A`;
4. `Q.A` -> `main`.

Direct `develop -> main`, implementation branch -> `Q.A`, and implementation branch -> `main` promotions are rejected by the repository validation workflows while this policy is active.

Q.A gates and sandbox requirements are documented in [`qa-policy.md`](qa-policy.md).

Repositories that intentionally use a different promotion model should adapt `.github/workflows/qa-source-branch.yml`, `.github/workflows/main-source-branch.yml`, the PR branch validator, and the PR Sync promotion exclusions together instead of changing only one layer.

## Trusted promotion gates

The `Q.A` and `main` source-branch gates are privileged metadata checks.

They use `pull_request_target` deliberately and **do not check out pull-request code**:

- `.github/workflows/qa-source-branch.yml` accepts only `develop -> Q.A`;
- `.github/workflows/main-source-branch.yml` accepts only `Q.A -> main`.

These workflows must remain metadata-only. Adding `actions/checkout`, shell execution from the PR head, or another path that executes untrusted head content under the `pull_request_target` token would violate the security contract.

The gate logic therefore reads the PR source/base refs from the event payload and exits without executing repository code from the proposed change.

## Source repository vs embedded target

The GPA source repository is identified explicitly by `.project-setup-source`.

The marker contains the source identity contract and is intentionally **not** distributed by the installer. A target repository containing files with names similar to GPA internals must not be misclassified as the source repository.

Embedded targets may preserve target-owned files such as an existing `Makefile` or workflow callers. Source-only caller/reference checks are skipped there while managed automation still remains subject to target-appropriate validation.

See [`project-setup-shared-tool.md`](project-setup-shared-tool.md) for the distribution boundary.

## PR automation and branch promotions

Implementation PR automation follows the same branch model:

```text
implementation branch -> develop -> Q.A -> main
```

PR Guardrails / PR metadata validation establishes the implementation PR context. PR Sync then synchronizes the linked task and Project metadata.

PR Sync excludes branch-promotion PRs by default:

- `develop -> Q.A`;
- `Q.A -> main`.

This prevents a promotion PR from inheriting task-specific labels, assignees, milestones, sub-issue relationships, or Project status.

See [`pr-sync.md`](pr-sync.md).

## Naming

Use lowercase implementation branch paths with hyphens, dots, underscores, or nested scopes, for example:

- `feat/project-setup`;
- `task/setup/customize-labels`;
- `fix/project-sync-pagination`;
- `ci/qa-validation-suite`.

`Q.A` is the deliberate exception because it is a named promotion branch rather than an implementation branch.
