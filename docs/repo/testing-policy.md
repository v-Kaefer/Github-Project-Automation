# Testing Policy (EN)

## Priority order

1. Automated deterministic test.
2. Automated live integration test in an isolated sandbox.
3. Smoke test.
4. Documented manual test when automation would leave permanent artifacts or introduce unacceptable risk.

## Validation layers

### Develop

Fast feedback for implementation work:

- repository quality checks;
- unit tests;
- static configuration validation;
- PR metadata and branch validation;
- CodeRabbit/review feedback when enabled.

### Q.A

Release-candidate validation:

- all deterministic checks from `develop`;
- supported Python compatibility matrix;
- Ubuntu, Windows, and macOS execution;
- package build/install verification;
- black-box installer and CLI tests;
- `.env`/Makefile portability tests;
- dry-run safety contract;
- live REST/GraphQL integration in a dedicated GitHub sandbox;
- idempotency checks for labels, milestones, and Project v2 synchronization;
- post-state verification and cleanup.

See [`qa-policy.md`](qa-policy.md) for exact jobs, Environment configuration, and required checks.

### Main

`main` receives code only after Q.A promotion. Main should avoid repeating the entire expensive Q.A matrix; it validates promotion source, normal repository checks, release metadata, and any release-specific smoke checks.

## Manual-only exception

Issue generation remains manual in Q.A until it becomes idempotent. The guarded workflow creates uniquely named resources in the sandbox, verifies them, closes them, and documents the remaining sandbox history.
