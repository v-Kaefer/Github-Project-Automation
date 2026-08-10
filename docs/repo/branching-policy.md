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

Repositories that intentionally use a different promotion model should adapt `.github/workflows/qa-source-branch.yml`, `.github/workflows/main-source-branch.yml`, and the PR branch validator together instead of changing only one layer.

## Naming

Use lowercase implementation branch paths with hyphens, dots, underscores, or nested scopes, for example:

- `feat/project-setup`;
- `task/setup/customize-labels`;
- `fix/project-sync-pagination`;
- `ci/qa-validation-suite`.

`Q.A` is the deliberate exception because it is a named promotion branch rather than an implementation branch.
