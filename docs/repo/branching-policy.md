# Branching Policy (EN)

## Default branches

- `main`: stable delivery branch.
- `develop`: optional integration branch.
- `phase/<phase-name>`: optional phase branch for staged delivery.
- implementation branches: `feat/`, `fix/`, `task/`, `docs/`, `refactor/`, `test/`, `chore/`, `ci/`, `hotfix/`, or `release/`.

## Default merge layers

1. implementation branch -> `develop` or a phase branch;
2. phase branch -> `develop`;
3. `develop` -> `main`;
4. `hotfix/*` -> `main` when explicitly allowed.

Repositories that use trunk-based development should adapt `.github/workflows/main-source-branch.yml` instead of copying this model unchanged.

## Naming

Use lowercase branch paths with hyphens, dots, underscores, or nested scopes, for example:

- `feat/project-setup`;
- `task/setup/customize-labels`;
- `fix/project-sync-pagination`;
- `hotfix/workflow-permissions`.
