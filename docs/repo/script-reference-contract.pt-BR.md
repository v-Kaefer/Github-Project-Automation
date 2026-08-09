# Contrato de referências dos scripts de validação

A configuração reutilizável distribui atualmente dois scripts de validação.

| Script | Chamado por | Distribuído por |
| --- | --- | --- |
| `scripts/validation/repo_quality.py` | `Makefile` (`quality` / `check`) | `project_setup/installer.py` |
| `scripts/validation/validate_pr_body.py` | `.github/workflows/pr-metadata.yml` | `project_setup/installer.py` |

O `repo_quality.py` valida esse contrato em cada execução de `make check`. Um novo arquivo `.py`, `.sh` ou `.ps1` dentro de `scripts/` precisa ser registrado com seu chamador antes que o quality gate possa passar.

A lista de namespaces legados é montada em tempo de execução. Isso evita que o validador interprete a própria lista de bloqueio como referência obsoleta, sem deixar de inspecionar o arquivo completo.
