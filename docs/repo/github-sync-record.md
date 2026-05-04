# GitHub Sync Record

This file records repository governance changes applied through local scripts and GitHub API operations.

## 2026-05-03

### Branch and PR
- Renamed the local planning branch from `copilot/research-project-files-planning` to `feat/research-project-files-planning`.
- Created the remote branch `feat/research-project-files-planning` pointing at commit `3d9eb392ccaf65ad2082454760d01f02c3428ed5`.
- Opened draft PR `#185` into `develop`.
- PR `#185` follows the repository PR template and includes `Closes #4` for US-00.
- Verified the PR issue-link workflow requires `Closes`, `Fixes`, or `Resolves` followed by an issue number.

### Milestones
- Created repository milestones `MS0` through `MS6` from `config/project/milestones.json`.
- Synced open planned issues to their repository milestones:
  - US/task issues under `MS0`: repository/bootstrap work.
  - US/task issues under `MS1`: phase 1 work.
  - US/task issues under `MS2`: phase 2 work.
  - US/task issues under `MS4`: phase 3/playtesting/stretch work.
  - US/task issues under `MS5`: phase 4/final build work.
  - US/task issues under `MS6`: stretch buffer/ranking-online work.
- Closed `not_planned` issues are considered duplicate or discarded planning entries and must not remain assigned to milestones.
- Corrected milestone counting by clearing milestones from 87 closed `not_planned` duplicate/discarded issues (`#98` through `#184`).
- Verified closed completed US-00 tasks `#5` through `#9` still keep `MS0`.
- Verified there are 0 closed `not_planned` issues with a milestone after cleanup.

### Project V2
- Found Project v2 `#4`: `Take Your Pills - Delivery Board`.
- Added generated issues to Project v2 from oldest to newest.
- Created missing custom fields from `config/project/project-definition.json`.
- Reordered Project items from oldest to newest after initial sync.
- Repaired or verified native sub-issue links using task body references such as `Parent story: ... (#N)`.
- Verified US-00 `#4` has five native sub-issues: `#5` through `#9`.
- Verified US-18 `#93` has four native sub-issues: `#94` through `#97`.

### Known follow-up
- Project v2 custom views listed in `config/project/project-definition.json` still require manual setup.
- The built-in Project `Status` field currently uses GitHub defaults (`Todo`, `In Progress`, `Done`) instead of the policy values in `config/project/project-definition.json`.
