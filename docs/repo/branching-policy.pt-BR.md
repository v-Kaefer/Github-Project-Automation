# Política de Branches (PT-BR)

## Branches padrão

- `main`: branch de entrega estável.
- `Q.A`: branch de release candidate e validação.
- `develop`: branch de integração.
- `phase/<nome-da-fase>`: branch opcional para entregas por fase.
- branches de implementação: `feat/`, `fix/`, `task/`, `docs/`, `refactor/`, `test/`, `chore/`, `ci/`, `hotfix/` ou `release/`.

## Camadas padrão de merge

1. branch de implementação -> `develop` ou branch de fase;
2. branch de fase -> `develop`;
3. `develop` -> `Q.A`;
4. `Q.A` -> `main`.

Promoções diretas `develop -> main`, branch de implementação -> `Q.A` e branch de implementação -> `main` são rejeitadas pelos workflows de validação enquanto esta política estiver ativa.

Os gates, testes e requisitos do sandbox estão documentados em [`qa-policy.pt-BR.md`](qa-policy.pt-BR.md).

Repositórios que adotarem outro modelo de promoção devem adaptar juntos `.github/workflows/qa-source-branch.yml`, `.github/workflows/main-source-branch.yml` e o validador de branch de PR, em vez de alterar apenas uma camada.

## Nomenclatura

Use caminhos de branches de implementação em letras minúsculas, com hífens, pontos, underscores ou escopos aninhados, por exemplo:

- `feat/project-setup`;
- `task/setup/customize-labels`;
- `fix/project-sync-pagination`;
- `ci/qa-validation-suite`.

`Q.A` é a exceção deliberada porque é uma branch nomeada de promoção, não uma branch de implementação.
