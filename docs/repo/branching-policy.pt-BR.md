# Política de Branches (PT-BR)

## Branches padrão

- `main`: branch de entrega estável.
- `develop`: branch de integração opcional.
- `phase/<nome-da-fase>`: branch opcional para entregas por fase.
- branches de implementação: `feat/`, `fix/`, `task/`, `docs/`, `refactor/`, `test/`, `chore/`, `ci/`, `hotfix/` ou `release/`.

## Camadas padrão de merge

1. branch de implementação -> `develop` ou branch de fase;
2. branch de fase -> `develop`;
3. `develop` -> `main`;
4. `hotfix/*` -> `main` quando explicitamente permitido.

Projetos que utilizam trunk-based development devem adaptar `.github/workflows/main-source-branch.yml`, em vez de copiar este modelo sem alterações.

## Nomenclatura

Use caminhos em letras minúsculas, com hífens, pontos, underscores ou escopos aninhados, por exemplo:

- `feat/project-setup`;
- `task/setup/customize-labels`;
- `fix/project-sync-pagination`;
- `hotfix/workflow-permissions`.
