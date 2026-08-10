# GitHub Projects v2 owner type

`project_setup` supports GitHub Projects v2 owned by either a personal GitHub account or a GitHub Organization.

## Setup option

Configure the owner type once in `.env` when Project v2 will be used:

```dotenv
# Personal GitHub account
PROJECT_SETUP_OWNER_TYPE=user
```

or:

```dotenv
# Company/team GitHub Organization
PROJECT_SETUP_OWNER_TYPE=organization
```

The documented values are `user` and `organization`. The implementation also accepts `org` and `company` as aliases for `organization` when resolving persistent configuration.

This setting is non-secret. It tells the GraphQL layer which GitHub namespace owns the Project v2 board. It does not change repository permissions and does not replace `PROJECT_SETUP_PAT`.

## Which value should I choose?

Use `user` when the repository owner is a personal GitHub account and the Project v2 board belongs to that account.

Use `organization` when the repository belongs to a company/team represented by a GitHub Organization and the Project v2 board belongs to that Organization.

Examples:

```dotenv
GITHUB_REPOSITORY=v-Kaefer/example
PROJECT_SETUP_OWNER_TYPE=user
```

```dotenv
GITHUB_REPOSITORY=Example-Company/example
PROJECT_SETUP_OWNER_TYPE=organization
```

## Auto-detection

`PROJECT_SETUP_OWNER_TYPE` may be left empty. During an authenticated Project v2 operation, `project_setup` queries the GitHub owner metadata first and resolves `User` or `Organization` before sending the Project GraphQL query.

Explicit configuration is recommended for predictable automation, while auto-detection preserves compatibility with older installations that do not yet contain this setting.

## Makefile behavior

The normal commands automatically inherit the value from `.env`:

```bash
make setup
make project-create
make project-sync
```

A one-off override can be supplied without editing `.env`:

```bash
make setup OWNER_TYPE=organization
make project-create OWNER_TYPE=user
```

The Makefile exports the resolved value as `PROJECT_SETUP_OWNER_TYPE`, so the Python CLI and Project v2 implementation use the same owner selection.

`make help` displays the resolved value. When it is empty, the output reports `auto-detect`.

## CLI behavior

The same selection is available directly in the Python CLI. The CLI deliberately exposes only the canonical values `user` and `organization`:

```bash
project-setup project create \
  --repo Example-Company/example \
  --owner-type organization \
  --live
```

```bash
project-setup project sync \
  --repo v-Kaefer/example \
  --project-number 3 \
  --owner-type user \
  --dry-run
```

The complete configured setup also accepts the option:

```bash
project-setup apply \
  --repo Example-Company/example \
  --owner-type organization \
  --dry-run
```

CLI `--owner-type` has precedence for that invocation. Without it, the implementation uses `PROJECT_SETUP_OWNER_TYPE`; if that is empty, authenticated Project v2 operations auto-detect the owner type.

## Diagnostics

`make help` shows the persistent/Make-resolved selection. `make doctor` reports:

```text
project_owner_type=user
```

or:

```text
project_owner_type=organization
```

When no type is configured, it reports:

```text
project_owner_type=auto-detect
```

An invalid configured value is a blocking `doctor` error with a corrective instruction.

## Authentication

Owner type and authentication are separate settings. Live Project v2 operations still require:

```dotenv
PROJECT_SETUP_PAT=...
```

For the current implementation, use a classic PAT with `repo` and `project` scopes. Never commit the token.

## Why this setting exists

GitHub GraphQL exposes Projects v2 under different fields for people and organizations: `user(...)` and `organization(...)`. Querying both for the same login can return a GraphQL error when the login exists only in one namespace.

`project_setup` therefore resolves the owner type first and queries only the matching namespace. This applies to Project creation, lookup, synchronization, Q.A validation, and cleanup.

## Q.A coverage

The test suite validates:

- explicit `user` selection;
- explicit `organization` selection;
- automatic User detection;
- automatic Organization detection;
- empty configuration falling back to auto-detection;
- environment selection taking precedence over auto-detection;
- CLI selection for `project create`, `project sync`, and `apply`;
- Makefile `.env` resolution and `OWNER_TYPE` override;
- live sandbox reuse of the resolved type during create, lookup, sync, and cleanup.
