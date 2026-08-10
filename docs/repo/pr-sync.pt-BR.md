# PR Sync

## Status

Este documento define o contrato de design da futura automação **PR Sync**.

A branch `feat/pr-sync` foi atualizada por fast-forward para o baseline atual de `main` antes da inclusão desta documentação. Neste estágio, a branch documenta o comportamento pretendido; a PR Sync ainda não está implementada.

PR Sync é o sucessor genérico, dentro do GitHub Project Setup, do workflow específico de repositório anteriormente chamado **PR Hygiene** no projeto de referência Take Your Pills.

## Objetivo

PR Sync mantém um pull request de implementação e seus itens de trabalho vinculados no GitHub sincronizados depois que o PR Guardrails resolve e valida o contexto do PR.

A ordem pretendida é:

```text
Evento de pull request
      |
      v
PR Guardrails
  - resolve o contexto
  - preenche metadata determinável
  - valida branch/body
      |
      v
PR Sync
  - sincroniza task/issue vinculada com o PR
  - sincroniza relação pai/sub-issue
  - sincroniza Project v2 e status
```

PR Sync não substitui PR Guardrails. Guardrails estabelece o contexto confiável; PR Sync consome esse contexto e aplica a sincronização.

## Responsabilidades planejadas

Quando habilitada pela configuração do repositório, PR Sync deverá poder:

- resolver a task de implementação através de `Closes #N`, `Fixes #N` ou `Resolves #N`;
- copiar famílias configuradas de labels da task para o PR;
- sincronizar o milestone do PR com a task ou contexto de entrega resolvido;
- sincronizar assignees quando permitido pela política do repositório;
- garantir que uma task com Story pai seja vinculada como sub-issue quando possível;
- adicionar a task ao GitHub Project v2 configurado quando ainda não estiver presente;
- sincronizar o Status do Project v2 conforme o ciclo de vida do PR;
- manter um único comentário marcado/sticky de PR Sync, sem duplicações.

## Mapeamento padrão do ciclo de vida

O mapeamento deve ser configurável. O contrato inicial é:

| Estado do PR | Status alvo no Project |
| --- | --- |
| Draft / convertido para draft | `In progress` |
| Ready for review / PR aberto e validado | `In review` |
| Fechado sem merge | `In progress` |
| Merged | `Done` |

Repositórios podem utilizar nomes de opções diferentes. PR Sync deve resolver aliases/opções configuradas em vez de depender de um schema específico do Take Your Pills.

## Pull requests de promoção

PR Sync é voltado principalmente a pull requests de implementação. PRs de promoção são transições de infraestrutura:

```text
develop -> Q.A -> main
```

Por padrão eles não devem ser tratados como tasks de implementação. A menos que o repositório habilite explicitamente sincronização de release/promoção, PR Sync deve ignorar sincronizações de task nesses caminhos.

Isso impede que um PR de promoção herde labels, assignees, relações de sub-issue ou status de Project pertencentes a uma única task de implementação.

## Direção de configuração

O schema definitivo será fechado durante a implementação. O formato pretendido é equivalente a:

```json
{
  "prAutomation": {
    "sync": {
      "enabled": true,
      "syncLabels": true,
      "syncMilestone": true,
      "syncAssignees": true,
      "linkSubissues": true,
      "syncProject": true,
      "skipPromotionPullRequests": true,
      "projectStatus": {
        "draft": "In progress",
        "review": "In review",
        "closed": "In progress",
        "merged": "Done"
      }
    }
  }
}
```

Este trecho é um exemplo de design e ainda não representa um schema de configuração consolidado.

## Autenticação e permissões

Sincronizações de PR/issue restritas ao repositório devem preferir o GitHub Actions token com as permissões mínimas necessárias. Operações em Project v2 podem exigir `PROJECT_SETUP_PAT`, dependendo do owner, localização do Project e capacidades do token.

Valores de PAT nunca devem aparecer em logs ou comentários.

Falhas em superfícies opcionais, como Project v2, devem produzir diagnóstico claro e não podem sobrescrever ou corromper metadata não relacionada do PR.

## Modelo de segurança

O workflow planejado deve usar automação confiável (`pull_request_target` ou workflow subsequente confiável) apenas quando não executar código não confiável do head do PR.

PR Sync deve:

- usar automação da base confiável quando checkout for necessário;
- não executar arquivos do head não confiável com permissões elevadas;
- usar o mínimo de permissões possível;
- ser idempotente para labels, milestone, assignees, Project, status e comentários sticky;
- tratar `403` e falhas de permissão como diagnóstico de sincronização, sem mascarar a causa original com traceback irrelevante.

## Relação com capacidades já existentes no GPA

O GPA já possui primitivas reutilizáveis que a PR Sync poderá compor, incluindo:

- manipulação de labels em issues/PRs;
- APIs de milestone;
- suporte a sub-issues;
- resolução do owner do Project v2;
- criação de item e sincronização de campos no Project v2;
- validação de PR e comentários marcados de validação.

A implementação deve reutilizar essas primitivas em vez de duplicar integrações com a API do GitHub.

## Relação com PR Guardrails

PR Guardrails é responsável por determinar o que pode ser inferido com segurança antes da validação. PR Sync deve rodar somente depois que esse estágio estabelecer com sucesso o contexto do PR.

Um PR típico deve seguir:

```text
feat/US-12-exemplo
      |
      v
PR Guardrails
  resolução de Story / task / milestone
  autofill do body
  validação
      |
      v
PR Sync
  task -> labels/milestone/assignee do PR
  Story <-> task
  task -> Project v2
  ciclo do PR -> Project Status
```

## Requisitos de validação antes da promoção

A implementação da PR Sync deve conter cobertura automatizada para pelo menos:

- task vinculada ausente;
- item vinculado é um PR em vez de issue/task;
- labels já existentes e ausentes;
- sincronização de milestone;
- sincronização de assignee e modo desabilitado;
- relação pai/sub-issue já existente e ausente;
- item de Project já existente e ausente;
- transições de status draft, review, closed e merged;
- PAT de Project ausente ou permissão insuficiente;
- comportamento de skip para PRs de promoção;
- execução repetida sem efeitos duplicados;
- limites de segurança para mesmo repositório e forks.

Comportamentos live envolvendo Project v2 devem usar o sandbox dedicado de Q.A, nunca o repositório-fonte.

## Nomenclatura

O nome genérico da funcionalidade e do workflow é **PR Sync**.

Não utilizar `PR Hygiene` em novos códigos, workflows, comandos CLI, configurações ou documentação do GPA, exceto em referências históricas ao comportamento avaliado no Take Your Pills.
