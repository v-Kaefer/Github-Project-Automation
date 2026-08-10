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

Repositórios que adotarem outro modelo de promoção devem adaptar juntos `.github/workflows/qa-source-branch.yml`, `.github/workflows/main-source-branch.yml`, o validador de branch e as exclusões de promoção da PR Sync, em vez de alterar apenas uma camada.

## Gates confiáveis de promoção

Os gates de origem para `Q.A` e `main` são verificações privilegiadas apenas de metadata.

Eles utilizam `pull_request_target` deliberadamente e **não fazem checkout do código do PR**:

- `.github/workflows/qa-source-branch.yml` aceita somente `develop -> Q.A`;
- `.github/workflows/main-source-branch.yml` aceita somente `Q.A -> main`.

Esses workflows devem permanecer metadata-only. Adicionar `actions/checkout`, executar shell vindo do head do PR ou qualquer caminho que execute conteúdo não confiável sob o token de `pull_request_target` quebra o contrato de segurança.

A validação lê apenas os refs de origem/destino do payload do evento e termina sem executar código da mudança proposta.

## Repositório-fonte vs target embarcado

O repositório-fonte do GPA é identificado explicitamente por `.project-setup-source`.

Esse marker contém o contrato de identidade do source e **não** é distribuído pelo instalador. Um target que possua arquivos com nomes semelhantes aos internos do GPA não deve ser confundido com o repositório-fonte.

Targets embarcados podem preservar arquivos próprios, como `Makefile` ou workflows callers existentes. Validações de referência/caller exclusivas do source são ignoradas nesse modo, enquanto a automação gerenciada continua sujeita às validações apropriadas ao target.

Veja [`project-setup-shared-tool.md`](project-setup-shared-tool.md).

## Automação de PR e promoções

A automação de implementação segue o mesmo fluxo:

```text
branch de implementação -> develop -> Q.A -> main
```

PR Guardrails / validação de metadata estabelece o contexto do PR de implementação. PR Sync então sincroniza task e metadata do Project.

Por padrão, PR Sync exclui PRs de promoção:

- `develop -> Q.A`;
- `Q.A -> main`.

Assim um PR de promoção não herda labels, assignees, milestone, sub-issue ou Status de Project pertencentes a uma task de implementação.

Veja [`pr-sync.pt-BR.md`](pr-sync.pt-BR.md).

## Nomenclatura

Use caminhos de branches de implementação em letras minúsculas, com hífens, pontos, underscores ou escopos aninhados, por exemplo:

- `feat/project-setup`;
- `task/setup/customize-labels`;
- `fix/project-sync-pagination`;
- `ci/qa-validation-suite`.

`Q.A` é a exceção deliberada porque é uma branch nomeada de promoção, não uma branch de implementação.
