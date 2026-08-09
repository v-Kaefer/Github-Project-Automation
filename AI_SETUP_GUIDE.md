# AI Setup Guide

This file is an operational contract for AI assistants configuring **GitHub Project Setup** for a user. It is intentionally procedural: do not reproduce the entire README or runbook to the user. Inspect the repository, determine the next safe action, explain only what the user needs at that moment, and verify the result before continuing.

## Mission

Guide the user through configuring and applying `project_setup` while preserving existing repository conventions and preventing accidental writes, duplicate resources, credential exposure, or overwrites.

The expected high-level flow is:

```text
inspect existing state
→ resolve configuration
→ doctor/check
→ discover
→ installation preview
→ inspect conflicts/customize
→ remote plan
→ explicit live confirmation
→ apply
→ verify final state
```

Do not skip directly to live execution.

## Operating rules

### 1. Inspect before asking

Before asking the user a question, check whether the answer already exists in the repository or configured environment.

Inspect, when available:

- `.env` / `.env.example` without exposing secret values;
- `project_setup.json`;
- `README*`, `CONTRIBUTING*`, `AGENTS.md`, project-specific instructions, and docs;
- `.github/workflows/`, issue templates, and PR templates;
- `config/project/` and `config/stories/`;
- current Git branch, status, and uncommitted changes;
- existing language/framework/build files;
- existing labels, milestones, issues, and Project v2 configuration when API access is available;
- whether a Project v2 owner is a personal GitHub user or GitHub Organization;
- existing naming, branching, release, testing, and governance conventions.

Prefer recorded repository facts over asking the user to repeat information.

If existing conventions conflict with the generic defaults, report the conflict and preserve the existing convention unless the user explicitly chooses to replace it.

### 2. Never request secrets in chat

Never ask the user to paste a PAT, `GITHUB_TOKEN`, `GH_TOKEN`, private key, or other credential into the conversation.

When a credential is required, give the exact setup instruction and then stop for the user to complete it privately.

For local Project v2 operations, instruct the user to store the PAT in `.env` as:

```dotenv
PROJECT_SETUP_PAT=...
```

For GitHub Actions Project v2 operations, instruct the user to create the repository secret `PROJECT_SETUP_PAT`.

For the current implementation, a classic PAT requires the `repo` and `project` scopes.

After the user says the credential was configured, verify only its **presence/status** with `make doctor` or equivalent diagnostics. Never print or retrieve the secret value.

### 3. Persistent identity is allowed; persistent mutation is not

The normal persistent configuration is:

```dotenv
PROJECT_SETUP_TARGET=../my-project
GITHUB_REPOSITORY=owner/repository
PROJECT_SETUP_OWNER_TYPE=user
PROJECT_SETUP_CONFIG=project_setup.json
PROJECT_SETUP_PROJECT_NUMBER=
```

For `PROJECT_SETUP_OWNER_TYPE`, use:

- `user` for a personal GitHub account;
- `organization` for a company/team represented by a GitHub Organization;
- empty only when authenticated auto-detection is intentionally preferred.

Use `PROJECT_SETUP_TARGET=.` when the tool is already embedded in the target repository.

`TARGET=...`, `REPO=...`, `CONFIG=...`, `PROJECT_NUMBER=...`, and `OWNER_TYPE=...` may be used as one-command overrides when necessary.

Do **not** recommend storing `LIVE=1` or `FORCE=1` in `.env`. Live mutation and overwrite decisions must remain explicit per invocation.

### 4. Re-read after user modifications

When the user says they changed a file, configured a secret, edited a manifest, resolved a conflict, or completed a manual GitHub step, do not continue based only on the statement.

Before the next stage, verify the relevant state again using the safest available source, for example:

- re-read the modified file;
- run `make doctor`;
- inspect `git diff` / `git status`;
- inspect the current GitHub resource through the API;
- rerun the relevant dry-run or plan.

If the resulting state differs from the previous assumptions, update the plan before continuing.

### 5. Stop at decision checkpoints

Pause and request explicit user confirmation when any of the following occurs:

- an existing repository convention conflicts with the generic setup;
- an existing managed file would need to be overwritten or substantially merged;
- `FORCE=1` would be required;
- the user must create or modify credentials/secrets;
- issue generation may overlap with existing issues/tasks;
- an existing Project v2 may make project creation unnecessary;
- the Project v2 owner type cannot be safely inferred and no explicit `PROJECT_SETUP_OWNER_TYPE` is recorded;
- a dry-run reports unexpected deletes, replacements, duplicates, or broad changes;
- any command would use `LIVE=1`;
- the intended operation cannot be verified safely.

Do not manufacture confirmation. A previous general request to “configure everything” is not sufficient authorization for an unexpected destructive or conflicting action discovered later.

## Step-by-step procedure

### Phase 0 — Establish context

Determine whether `project_setup` is:

- being run from its standalone repository against another local target; or
- already embedded inside the target repository.

Inspect the current repository state and any existing instructions before proposing commands.

Check for uncommitted changes. If unrelated user changes exist, preserve them and avoid overwriting their files.

### Phase 1 — Resolve `.env` defaults

Check whether `.env` exists and whether the non-secret target identity is configured.

Required for the shortest Makefile flow:

```dotenv
PROJECT_SETUP_TARGET=...
GITHUB_REPOSITORY=owner/repository
```

For repositories that use GitHub Projects v2, resolve the owner type before Project operations:

```dotenv
PROJECT_SETUP_OWNER_TYPE=user
```

or:

```dotenv
PROJECT_SETUP_OWNER_TYPE=organization
```

If the owner can be verified from GitHub metadata, do not ask the user unnecessarily. Record the correct value when persistent predictability is desired. If the variable is intentionally left empty, explain that authenticated Project v2 operations will auto-detect the owner type before GraphQL lookup.

Optional:

```dotenv
PROJECT_SETUP_CONFIG=project_setup.json
PROJECT_SETUP_PROJECT_NUMBER=
```

If values are missing, ask the user only for the information that cannot be inferred. If the repository URL/path already establishes the value, use it rather than asking again.

After configuration, verify with:

```bash
make help
make doctor
```

Confirm that the resolved target, repository, and Project owner type are the intended ones before proceeding.

### Phase 2 — Validate the tool and local state

Run or ask the user to run:

```bash
make doctor
make check
```

If the AI has execution access, execute these directly and summarize only actionable failures.

For each failure:

1. identify the exact cause;
2. inspect the referenced file/state;
3. provide the smallest corrective action;
4. apply it only when authorized and safe;
5. rerun the failing validation.

Do not proceed while `doctor` reports a blocking configuration problem or `check` reports repository-quality/test failures unless the user explicitly chooses to defer a known non-blocking item.

### Phase 3 — Discover existing patterns

Run:

```bash
make discover
```

Treat discovery as a starting point, not as authority over existing project conventions.

Before proposing configuration changes, compare discovery with recorded repository patterns such as:

- stack/language/build system;
- branch naming and protected branches;
- existing labels and milestone naming;
- issue/story/task conventions;
- PR sections and validation rules;
- existing automation workflows;
- existing Project v2 boards, owner type, and fields.

If a pattern already exists, prefer adapting `project_setup` to it rather than replacing it.

Tell the user only about decisions that actually require their input.

### Phase 4 — Preview installation

Run:

```bash
make init-dry
```

Inspect the proposed file list and any skipped existing files.

If files already exist:

1. read the existing file;
2. compare it with the project setup template;
3. determine whether the setup can preserve it as-is, needs a merge, or has a true conflict;
4. explain that specific decision to the user.

Never jump directly to `FORCE=1`. Prefer a deliberate merge that preserves target-repository behavior.

When the preview is understood, the normal local installation is:

```bash
make init
```

After installation, inspect `git status` and `git diff` before continuing.

### Phase 5 — Review and customize manifests

Review the installed/configured files against the repository's actual conventions:

- `project_setup.json`;
- `config/project/labels.json`;
- `config/project/milestones.json`;
- `config/project/project-definition.json`;
- `config/stories/backlog-manifest.json`;
- installed workflows and templates.

Do not enable issue generation or Project creation merely because the modules exist.

If the user must edit values manually, provide the exact file and decisions needed, then wait. When they finish, re-read the files and verify the changes before moving on.

### Phase 6 — Check remote state before planning creation

When API access is available, inspect existing GitHub resources before recommending creation.

#### Issues and tasks

Issue generation is currently **not idempotent**. Before any live issue generation:

- inspect/search existing issues for matching story/task identifiers, titles, or content;
- compare them with `config/stories/backlog-manifest.json`;
- report potential duplicates;
- stop for confirmation if overlap exists.

Do not run live issue generation repeatedly just to “make sure it worked.” Verify the created issues instead.

#### Projects v2

Before `project-create`, determine the Project owner namespace:

- personal account → `PROJECT_SETUP_OWNER_TYPE=user`;
- GitHub Organization/company → `PROJECT_SETUP_OWNER_TYPE=organization`.

If the value is missing but API access is available, inspect GitHub owner metadata first. Never query both `user(...)` and `organization(...)` GraphQL namespaces for one login merely to discover which one works; the implementation intentionally resolves the owner type before the Project query.

Then check whether the intended Project already exists when possible.

If it exists:

- do not create a duplicate;
- identify its Project number;
- store/recommend `PROJECT_SETUP_PROJECT_NUMBER=<number>`;
- prefer `project-sync` after reviewing the plan.

If Project v2 access requires a PAT, guide the user through private PAT setup and wait for completion. Then verify status, not value.

### Phase 7 — Produce the dry-run plan

Run:

```bash
make plan
```

or the appropriate individual dry-run, such as:

```bash
make labels
make milestones
make issues
make project-create
make project-sync
```

Summarize the plan in terms of user-visible effects:

- what would be created;
- what would be updated;
- what would be skipped/unchanged;
- the resolved Project owner type when Project v2 is involved;
- anything ambiguous or conflicting;
- anything that cannot currently be verified.

Do not bury important changes inside raw logs.

If the plan differs from the user's intent or existing conventions, correct configuration and rerun the dry-run instead of proceeding live.

### Phase 8 — Live checkpoint

Immediately before any live command, verify again:

- resolved `PROJECT_SETUP_TARGET`;
- resolved `GITHUB_REPOSITORY`;
- resolved `PROJECT_SETUP_OWNER_TYPE` when Project v2 is involved;
- active configuration file;
- Project number when relevant;
- current Git status/diff when local files are involved;
- latest dry-run output;
- absence/resolution of duplicate/conflict warnings;
- required credential status.

Then tell the user exactly what the live command will change and ask for explicit confirmation.

Only after confirmation use commands such as:

```bash
make apply LIVE=1
```

or an explicitly selected module:

```bash
make labels LIVE=1
make milestones LIVE=1
make issues LIVE=1
make project-create LIVE=1
make project-sync LIVE=1
```

Do not use `LIVE=1` as a troubleshooting step.

### Phase 9 — Verify applied results

After a live operation, verify the resulting state instead of assuming success from the process exit code alone.

Depending on the module, verify:

- labels/milestones now match the manifests;
- expected issues/tasks exist exactly once;
- sub-issue links are correct;
- the expected Project v2 exists under the intended user/organization owner and has the intended number/fields/items;
- local installed files are present;
- no unrelated files were modified.

Run relevant diagnostics again:

```bash
make doctor
make check
```

Use `git status` / `git diff` to show local changes that the user may want to review and commit.

## How to communicate with the user

Keep interaction incremental. At each turn, provide:

1. **what was verified**;
2. **what was found**;
3. **the next action only**;
4. **whether the user must do something or whether the AI can continue**.

Do not paste the entire setup manual unless the user asks for it.

Good interaction example:

```text
I found an existing PR template with two project-specific sections that the generic template does not contain. I will preserve those sections and merge only the project_setup validation fields.

Before I continue, please confirm that the existing PR template is authoritative for this repository.
```

Good Project owner example:

```text
The repository owner is a GitHub Organization, so Project v2 should use PROJECT_SETUP_OWNER_TYPE=organization. I verified that setting in the resolved setup and can continue to the Project dry-run.
```

Good credential checkpoint:

```text
Project v2 is enabled, but PROJECT_SETUP_PAT is not configured. Create a classic PAT with `repo` and `project`, save it privately as PROJECT_SETUP_PAT in .env, and tell me when that is done. Do not paste the token here.
```

After the user replies that it is done, verify with `make doctor` before continuing.

## What the AI must not do

- Do not request secret values in conversation.
- Do not expose secret values found in files, environment variables, command output, or APIs.
- Do not use `LIVE=1` without a fresh, explicit live checkpoint.
- Do not persist `LIVE=1` or `FORCE=1` in `.env`.
- Do not use `FORCE=1` before inspecting the existing files and receiving confirmation.
- Do not replace established repository conventions simply because generic defaults differ.
- Do not guess the Project owner namespace when it can be verified.
- Do not query both GraphQL owner namespaces for one login as a discovery mechanism.
- Do not create duplicate Projects when an intended Project already exists.
- Do not repeat live issue generation without checking for existing generated issues.
- Do not assume a manual user change occurred; verify it.
- Do not assume the repository stayed unchanged between turns; re-check relevant state before a consequential action.
- Do not treat a dry-run as proof that a later live run succeeded; verify after application.

## Supporting documentation

Use these files for deeper implementation details only when needed:

- `README.md` — concise user-facing overview and commands;
- `README.pt-BR.md` — Portuguese user-facing version;
- `docs/repo/project-owner-type.md` — Project v2 user/organization owner selection and auto-detection;
- `docs/repo/project-owner-type.pt-BR.md` — Portuguese Project v2 owner-selection guide;
- `docs/repo/project-setup-runbook.pt-BR.md` — detailed human operational runbook;
- `docs/repo/project-setup-shared-tool.md` — package/distribution and authentication boundaries;
- `docs/DOCUMENTATION-GUIDE.md` — authoritative documentation map.

This AI guide governs the **interaction sequence**. Repository-specific instructions and recorded conventions remain authoritative for repository-specific decisions.