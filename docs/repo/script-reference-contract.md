# Validation script reference contract

The reusable setup currently distributes two validation scripts.

| Script | Invoked by | Distributed by |
| --- | --- | --- |
| `scripts/validation/repo_quality.py` | `Makefile` (`quality` / `check`) | `project_setup/installer.py` |
| `scripts/validation/validate_pr_body.py` | `.github/workflows/pr-metadata.yml` | `project_setup/installer.py` |

`repo_quality.py` validates this contract on every `make check` run. A new `.py`, `.sh`, or `.ps1` file under `scripts/` must be registered with its caller before the quality gate can pass.

The legacy namespace list is assembled at runtime. This prevents the validator from reporting its own deny-list definitions as obsolete references while still scanning the complete file.
