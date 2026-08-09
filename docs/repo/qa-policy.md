# Q.A Validation Policy

## Promotion flow

The release flow is intentionally linear:

```text
implementation branch -> develop -> Q.A -> main
```

- implementation branches are integrated into `develop`;
- only `develop` may open a promotion PR to `Q.A`;
- only `Q.A` may open a promotion PR to `main`;
- `main` should not receive direct feature or hotfix promotion while this policy is enabled.

The source restrictions are enforced by:

- `.github/workflows/qa-source-branch.yml`;
- `.github/workflows/main-source-branch.yml`;
- `project_setup.pr_validation.validate_branch`.

## Q.A gate 1: deterministic validation

`.github/workflows/qa-validation.yml` runs on pull requests and pushes targeting `Q.A`.

It validates:

- the complete `make check` suite on Ubuntu / Python 3.11;
- Python 3.11, 3.12, 3.13, and 3.14 on Ubuntu;
- Python 3.11 and 3.14 on Windows;
- Python 3.11 and 3.14 on macOS;
- installation of GNU Make on the Windows runner;
- package installation and `pip check`;
- all documented CLI entrypoints;
- Q.A black-box installer and dry-run tests;
- Makefile `.env` resolution and command-line override behavior;
- `make doctor` in read-only mode;
- wheel and source-distribution builds;
- installation of the built wheel in a clean virtual environment.

This workflow must not require GitHub write credentials.

## Q.A gate 2: live sandbox validation

`.github/workflows/qa-live.yml` runs after a push to `Q.A` and can also be dispatched manually.

It uses a dedicated GitHub Environment named `qa`.

Configure the Environment with:

| Type | Name | Value |
| --- | --- | --- |
| Environment variable | `QA_REPOSITORY` | Dedicated disposable repository in `owner/repository` format |
| Environment secret | `QA_PROJECT_SETUP_PAT` | PAT with the repository and Project v2 permissions required by the current implementation |

The workflow maps `QA_PROJECT_SETUP_PAT` to `PROJECT_SETUP_PAT` only inside the live test job. Secret values are never printed.

The source repository must never be used as `QA_REPOSITORY`; the workflow and test script reject that configuration.

### Live resources tested

Each run creates uniquely named temporary resources:

- one label;
- one milestone;
- one Project v2 with custom fields.

For labels and milestones, the test performs create -> verify -> update -> verify -> repeat sync -> verify a single resource remains.

For Project v2, the test creates the Project, synchronizes it twice, verifies custom fields are not duplicated, and reads the remote state after synchronization.

The live workflow removes the temporary label, milestone, and Project before finishing. Cleanup failures fail the Q.A job.

## Manual issue-generation test

Issue generation is not idempotent yet and GitHub issues are not normally deletable. It is therefore excluded from the automatic Q.A gate.

`.github/workflows/qa-issue-generation.yml` is manual-only and requires the exact confirmation:

```text
RUN_NON_IDEMPOTENT_TEST
```

It creates a uniquely named story and task in the dedicated sandbox, verifies the parent reference, closes both as `not_planned`, and restores any labels it temporarily changed or created.

The two closed Q.A issues remain visible in sandbox history by design.

## Recommended required checks

For PRs into `Q.A`, require at least:

- `validate-qa-source`;
- `repository-quality / ubuntu / py3.11`;
- every `compatibility / ...` matrix result;
- `package-artifact / wheel-and-sdist`.

After the `qa` Environment is configured and stable, also require the live sandbox workflow before promotion from `Q.A` to `main`.

For PRs into `main`, require:

- `validate-main-source`;
- the normal repository/PR metadata checks;
- evidence that the exact Q.A commit passed the Q.A validation and live sandbox gates.

## Failure policy

A Q.A failure blocks promotion. Fixes return to an implementation branch or `develop`; do not patch `Q.A` directly unless the repository policy is explicitly changed.
