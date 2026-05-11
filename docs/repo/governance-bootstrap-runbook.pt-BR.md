# Runbook — Governance Bootstrap

## 1) Required permissions
To create/edit Project, labels, issues and sub-issues automatically, use an account with:
- **Admin** access to the repository
- Permission for **Projects** (Project v2)
- Token with scopes: `repo`, `project` and `read:org` (if the repo is in an org)

## 2) How to grant admin access on GitHub
1. Repository → **Settings** → **Collaborators and teams**.
2. Add the user/account that will run the automations.
3. Set role to **Admin**.
4. Under **Settings → Actions → General**, enable:
   - `Read and write permissions` for the `GITHUB_TOKEN`;
   - creation and approval of PRs by GitHub Actions (if desired).
5. To create **Project v2**, authenticate `gh` with a PAT that includes the `project` scope (plus `repo`).

## 3) How to run

### Option A — Manual workflow (recommended)
1. Push this branch.
2. GitHub → **Actions** → `Governance bootstrap (manual)` → **Run workflow**.
3. Run with `dry_run=true` first to preview.
4. Run with `dry_run=false` to apply labels, milestones, issues/tasks/sub-issues and Project.

### Option B — Local CLI
> Security: avoid putting your PAT directly in shell history. Prefer loading via a local unversioned env file, secret manager, or interactive prompt.

```bash
export GH_TOKEN=<your-PAT-with-project-scope>
export GITHUB_REPOSITORY=owner/repo

# Preview changes
python -m governance_bootstrap bootstrap --repo owner/repo --dry-run

# Apply
python -m governance_bootstrap bootstrap --repo owner/repo --no-dry-run
```

Or use the guided `discover` wizard:

```bash
python -m governance_bootstrap discover --repo owner/repo --config governance.bootstrap.json
```

## 4) Notes
- To reuse in another project, copy and adapt the manifests in `config/project`, `config/stories` and `governance.bootstrap.json`.
- The expected workflow secret is `GOVERNANCE_PAT`.
- The `discover` command checks auth status, detects project type, and prints the recommended bootstrap command.
- Milestone responsible pairs are `TBD` in `config/phases/phase-review-policy.json` — fill them in for your team.

