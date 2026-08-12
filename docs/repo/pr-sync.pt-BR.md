# PR Sync

## Status

**Implementado.**

PR Sync é o lane de sincronização pós-Guardrails do GPA. O workflow público é `.github/workflows/pr-sync.yml`; `project_setup.pr_sync_router` escolhe entre:

```text
PR de implementação -> project_setup.pr_sync
PR de promoção      -> project_setup.promotion_sync
```

A sincronização normal acontece somente depois de Guardrails bem-sucedido via `workflow_run`, e cada caminho relê o PR vivo em vez de depender do payload antigo do webhook.

## Pipeline

```text
Evento de PR
  -> Autofill
  -> Guardrails no PR vivo
  -> workflow_run após sucesso
  -> PR Sync Router
       -> Implementation Sync
       -> Promotion Sync
```

Eventos de lifecycle também entram diretamente no router:

- `ready_for_review`;
- `converted_to_draft`;
- `closed`.

## Implementation Sync

PRs de implementação identificam uma issue/task canônica através de:

```text
Closes #123
Fixes #123
Resolves #123
```

A task pode dirigir:

- famílias configuradas de labels no PR;
- milestone do PR;
- assignees do PR;
- relação pai/sub-issue;
- membership/status da task no Project v2.

Se a task estiver sem assignee e `assignAuthorWhenTaskUnassigned` estiver habilitado, o autor pode ser atribuído à task e ao PR.

## Promotion Sync

Promotion paths não são pulados. Eles são roteados para sincronização agregada.

Caminhos versionados:

```text
develop -> Q.A
Q.A -> main
```

O manifesto `## Related PRs` é autoritativo depois do Guardrails. Promotion Sync nunca escolhe a primeira issue vinculada como falsa task canônica.

Ele possui quatro responsabilidades:

1. agregar metadata nativa de todos os PRs constituintes;
2. aplicar a metadata no próprio PR de promoção;
3. adicionar/atualizar o próprio PR de promoção no Project v2 quando configurado;
4. manter backlinks específicos por estágio nos PRs constituintes.

### Agregação de metadata nativa

As famílias gerenciadas de labels exigem consenso. Defaults:

```text
type:
priority:
test:
```

Se todos os Related PRs possuírem o mesmo valor único em uma família, a promoção recebe essa label. Ausência/divergência faz a família gerenciada ficar sem valor; o comentário sticky do Promotion Sync registra o conflito. Labels manuais/não gerenciadas são preservadas.

Milestone também exige acordo unânime. O GPA não escolhe um milestone arbitrariamente em caso de conflito.

Assignees são multi-value e usam a união deduplicada dos assignees de todos os Related PRs.

### Membership da promoção no Project v2

Implementation Sync mantém as tasks como itens de trabalho do Project. Promotion Sync passa a adicionar também o **próprio PR de promoção** ao Project configurado, permitindo representar o lifecycle de review/release e preencher o campo nativo `Projects` no sidebar do PR.

Lifecycle default:

| Estado do PR | Project Status |
| --- | --- |
| Draft | `In progress` |
| Open / review | `In review` |
| Fechado sem merge | `In progress` |
| Mergeado | `Done` |

Operações de Project exigem `PROJECT_SETUP_PAT` e `PROJECT_SETUP_PROJECT_NUMBER`. A metadata normal do PR continua sincronizando se o Project não estiver configurado.

## Related PR Detection

`project_setup.related_prs` é responsável por descoberta, Autofill e validação da promoção.

O detector une e deduplica:

1. PRs mergeados cujas branches correspondem aos regex configurados;
2. referências explícitas nas seções configuradas do body;
3. referências herdadas de promoções anteriores.

Patterns default:

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

O repositório pode substituir a lista inteira no `project_setup.json`.

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

As mesmas flags `syncLabels`, `syncMilestone`, `syncAssignees` e `syncProject` controlam implementation e promotion; o modo de promoção muda a semântica de agregação, não a superfície de configuração.

## Autenticação e permissões

Sincronização dentro do repositório usa `${{ github.token }}` com:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: write
```

`PROJECT_SETUP_PAT` fica reservado às operações opcionais de GitHub Projects v2.

## Idempotência

Implementation Sync converge sem duplicar labels, assignees, membership de Project, relações pai/sub-issue ou o comentário marcado.

Promotion Sync:

- substitui somente famílias gerenciadas de labels e preserva labels externas;
- converge milestone para o consenso agregado;
- adiciona assignees faltantes sem duplicatas;
- reutiliza membership existente do Project quando visível;
- atualiza Status no mesmo item;
- atualiza backlinks/comentários por marker em vez de duplicá-los.

## Validação live

O lane protegido `Q.A -> main` valida três níveis:

1. criação/atualização/idempotência/cleanup de recursos;
2. Implementation PR Sync contra base não-default;
3. Promotion Sync com PRs constituintes realmente mergeados.

O smoke de promoção falha se o **próprio objeto do PR de promoção** não possuir labels, milestone, assignees, membership/status no Project v2 e convergência correta após merge. Comentário sticky verde, sozinho, não é evidência suficiente.

Veja `pr-governance-architecture.pt-BR.md` para o modelo Mermaid.
