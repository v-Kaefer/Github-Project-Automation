# PR Sync

## Status

**Implementado.**

PR Sync é o fluxo de sincronização executado após Guardrails no GPA. Ele agora possui dois contextos distintos:

- **Implementation Sync** — uma issue/task canônica;
- **Promotion Sync** — um manifesto agregado de pull requests relacionados.

O workflow público continua sendo `.github/workflows/pr-sync.yml`, enquanto `project_setup/pr_sync_router.py` escolhe o modo correto.

## Pipeline

```text
Evento de PR
  -> Autofill
  -> Guardrails
  -> workflow_run em caso de sucesso
  -> PR Sync Router
       -> Implementation Sync
       -> Promotion Sync
```

PR Sync não depende de uma cópia alterada do payload original. No fluxo normal pós-Guardrails, o pull request vivo é buscado novamente.

## Implementation Sync

PRs de implementação usam `project_setup/pr_sync.py`.

A issue/task vinculada é identificada por closing reference:

```text
Closes #123
Fixes #123
Resolves #123
```

A task pode fornecer:

- famílias configuradas de labels;
- milestone;
- assignees;
- relação pai/sub-issue;
- membership/status opcional no Project v2.

Se a task estiver sem assignee e `assignAuthorWhenTaskUnassigned` estiver habilitado, o autor do PR pode ser atribuído à task e sincronizado com o PR.

### Lifecycle padrão no Project

| Estado do PR | Status alvo |
| --- | --- |
| Draft / convertido para draft | `In progress` |
| Ready for review / PR validado e aberto | `In review` |
| Fechado sem merge | `In progress` |
| Merged | `Done` |

Operações de Project v2 continuam opcionais e usam `PROJECT_SETUP_PAT`. Mutações comuns de PR/issues usam o token nativo do Actions.

## Promotion Sync

Promotion paths não são mais ignorados pelo workflow. Eles são roteados para Promotion Sync agregado.

Caminhos versionados:

```text
develop -> Q.A
Q.A -> main
```

Promotion Sync **não** seleciona uma primeira issue/task arbitrária. Ele lê o manifesto `## Related PRs` e mantém backlinks idempotentes entre os PRs relacionados e a promoção atual.

Exemplo:

```text
feature/fix PRs -> develop
        |
        v
develop -> Q.A
        |
        v
Promotion Sync registra os PRs relacionados em Q.A
        |
        v
Q.A -> main
        |
        v
Promotion Sync registra o vínculo com main
```

A descoberta de PRs e o Autofill do body de promoção acontecem antes de Guardrails em `project_setup.related_prs`; consulte `pr-governance-architecture.pt-BR.md`.

## Related PR Detection

O detector une e deduplica:

1. PRs mergeados cuja branch head corresponde aos regexes configurados;
2. referências de PR explicitamente informadas em seções configuradas do body;
3. referências herdadas de promotion PRs anteriores mergeados na branch-fonte atual.

Os patterns default são propositalmente amplos como exemplos:

```text
^feat/
^fix/
^docs/
^refactor/
^test/
^hotfix/
^phase/
^task/
^chore/
^ci/
^release/
```

O repositório pode substituir a lista inteira. Referências explícitas no body continuam válidas mesmo quando a branch do PR referenciado não corresponde aos patterns.

## Configuração

```json
{
  "prAutomation": {
    "relatedPrs": {
      "enabled": true,
      "branchPatterns": [
        "^feat/",
        "^fix/",
        "^docs/",
        "^refactor/",
        "^test/",
        "^hotfix/",
        "^phase/",
        "^task/",
        "^chore/",
        "^ci/",
        "^release/"
      ],
      "bodySections": ["Related PRs", "Related Pull Requests"],
      "includeBranchMatches": true,
      "includeBodyReferences": true,
      "inheritBodyReferences": true,
      "fallbackDays": 7
    },
    "sync": {
      "enabled": true,
      "syncLabels": true,
      "labelPrefixes": ["type:", "priority:", "test:"],
      "syncMilestone": true,
      "syncAssignees": true,
      "assignAuthorWhenTaskUnassigned": true,
      "linkSubissues": true,
      "syncProject": true,
      "promotionPaths": [
        {"head": "develop", "base": "Q.A"},
        {"head": "Q.A", "base": "main"}
      ],
      "projectStatusField": "Status",
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

`promotionPaths` agora são regras de roteamento. A configuração versionada não expõe mais `skipPromotionPullRequests`.

## Modelo de eventos

Sincronização normal roda por `workflow_run` depois de `PR metadata validation` concluir com sucesso.

Eventos de lifecycle que exigem transição direta também entram pelo router via `pull_request_target`:

- `ready_for_review`;
- `converted_to_draft`;
- `closed`.

Os dois caminhos usam automação confiável da base. Forks são excluídos das mutações privilegiadas.

## Autenticação e permissões

Sincronização restrita ao repositório usa `${{ github.token }}` com:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: write
```

`PROJECT_SETUP_PAT` fica reservado às operações opcionais de GitHub Projects v2. Related PR Detection, Autofill/validação de promoção e backlinks não dependem desse PAT.

## Idempotência

Implementation Sync converge sem duplicar labels, assignees, Project membership, relações pai/sub-issue ou comentário marcado.

Promotion Sync usa comentários marcados específicos por estágio, de forma que execuções repetidas atualizam o vínculo existente em vez de criar duplicatas.

## Modelo de segurança

- somente automação confiável da base/default branch;
- nenhum código não confiável do head roda com credenciais de escrita;
- `persist-credentials: false` nos checkouts privilegiados;
- sucesso de Guardrails é obrigatório antes da sincronização normal;
- estado vivo do PR é buscado novamente entre etapas que alteram e consomem estado;
- Related PRs são validados como PRs realmente mergeados antes da promoção;
- credenciais do Project v2 ficam isoladas das mutações comuns do repositório.

## Instalação

O instalador distribui `.github/workflows/pr-sync.yml`. Os módulos Python sob `project_setup/*.py` incluem:

```text
pr_sync.py
pr_sync_router.py
related_prs.py
```

Arquivos existentes no target continuam sujeitos ao comportamento preserve-by-default do instalador.

## Validação

A cobertura fica dividida em:

- `tests/test_pr_sync.py` — sincronização de implementação e segurança do workflow;
- `tests/test_pr_sync_autofill.py` — ordenação do Autofill de implementação;
- `tests/test_related_prs.py` — detecção por branch/body, patterns configuráveis, agregação do body de promoção e dispatch do router.

Comportamento live de Project v2 e integração Q.A continuam responsabilidades do sandbox, não de testes destrutivos no repositório-fonte.
