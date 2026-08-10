# PR Sync

## Status

**Implementado.**

PR Sync é a automação genérica do GitHub Project Setup que mantém um pull request de implementação alinhado com sua issue/task vinculada e, quando configurado, com o GitHub Projects v2.

A implementação é composta por:

- `.github/workflows/pr-sync.yml` — orquestração confiável no GitHub Actions;
- `project_setup/pr_sync.py` — lógica de sincronização;
- `project_setup.json` → `prAutomation.sync` — política/configuração do repositório;
- `tests/test_pr_sync.py` — testes unitários e de contrato do workflow.

A funcionalidade é o sucessor genérico do workflow específico anteriormente chamado **PR Hygiene** no repositório de referência Take Your Pills. Novos códigos e documentos do GPA usam **PR Sync**.

## Limite de responsabilidade

PR Sync não substitui PR Guardrails.

O pipeline esperado é:

```text
Evento de pull request
      |
      v
PR Guardrails / validação atual de metadata do PR
  - resolve ou valida o contexto confiável
  - valida contrato de branch/body
      |
      v
PR Sync
  - resolve a task de implementação vinculada
  - sincroniza metadata task -> PR
  - sincroniza relação pai/sub-issue
  - sincroniza task -> Project v2
  - sincroniza ciclo do PR -> Status do Project
```

O workflow atual do GPA chama-se `PR metadata validation`. PR Sync escuta sua conclusão com sucesso e também reconhece o nome compatível `PR guardrails`, permitindo a futura promoção do Guardrails ao nome genérico sem quebrar a orquestração.

## Modelo de eventos

Atualizações normais de implementação rodam via `workflow_run` depois que a validação confiável/Guardrails termina com sucesso.

Eventos de ciclo de vida que não precisam de outra validação rodam diretamente por `pull_request_target`:

- `converted_to_draft`;
- `closed`.

Os dois caminhos usam automação da base confiável. O workflow não executa código do head não confiável com permissões de escrita.

PRs vindos de forks são ignorados.

## Task de implementação vinculada

PR Sync resolve a issue/task por uma referência de fechamento no body do PR:

```text
Closes #123
Fixes #123
Resolves #123
```

Se não houver referência, PR Sync cria ou atualiza um único comentário marcado de status e retorna falha para a etapa de sincronização.

Se o item referenciado for outro pull request, ele é rejeitado como task de implementação.

A própria referência de fechamento estabelece o vínculo Development do GitHub entre PR e issue/task. PR Sync usa esse vínculo canônico como contexto, em vez de criar uma associação paralela.

## Sincronização de metadata

Por padrão, a task vinculada é a fonte para estes campos do PR.

### Labels

Famílias configuradas de labels são copiadas quando estiverem ausentes.

Prefixos padrão:

```text
type:
priority:
test:
```

A operação é aditiva: PR Sync não remove labels não relacionados ou antigos do PR.

### Milestone

Se a task possuir milestone diferente do PR, o milestone do PR é atualizado para o da task.

### Assignees

Assignees existentes na task são adicionados ao PR quando estiverem ausentes.

Se a task estiver sem assignee e `assignAuthorWhenTaskUnassigned` estiver habilitado, o autor do PR é atribuído à task e então sincronizado com o PR.

Cada comportamento pode ser desabilitado na configuração.

## Story pai / sub-issue

Tasks geradas pelo GPA já utilizam referência de pai, por exemplo:

```text
Parent story: US-12 (#45)
```

Com `linkSubissues` habilitado, PR Sync resolve o número da Story/issue pai e garante que a task seja vinculada como sub-issue.

Execuções repetidas tratam relações já existentes como idempotentes. Falhas de permissão são apresentadas como diagnóstico, sem tentar duplicar a mutação.

## Sincronização com Project v2

Quando estão configurados:

- `syncProject: true`;
- variável de Actions `PROJECT_SETUP_PROJECT_NUMBER`;
- secret de Actions `PROJECT_SETUP_PAT`;

PR Sync garante que a task vinculada pertença ao Project v2 configurado e atualiza o campo single-select de status.

A resolução de owner reutiliza o contrato já existente do GPA. `PROJECT_SETUP_OWNER_TYPE` pode ser fornecido como variável de Actions quando for necessário fixar `user` ou `organization`.

Sem Project number ou PAT, a sincronização de PR/task dentro do repositório continua funcionando e o comentário sticky informa por que o Project foi ignorado.

## Mapeamento padrão do ciclo de vida

| Estado do PR | Status alvo no Project |
| --- | --- |
| Draft / convertido para draft | `In progress` |
| Ready for review / PR aberto validado | `In review` |
| Fechado sem merge | `In progress` |
| Merged | `Done` |

O nome do campo e das opções são configuráveis. O GPA resolve a opção pelo nome normalizado, sem depender de um schema específico do Take Your Pills.

## PRs de promoção

PR Sync é voltado a PRs de implementação, não à infraestrutura de promoção de branches.

Os caminhos ignorados por padrão são:

```text
develop -> Q.A
Q.A -> main
```

Eles são ignorados antes da resolução de task ou qualquer mutação. Repositórios com outro modelo podem substituir `promotionPaths` ou desabilitar `skipPromotionPullRequests`.

## Schema de configuração consolidado

`project_setup.json` agora contém o contrato ativo:

```json
{
  "prAutomation": {
    "sync": {
      "enabled": true,
      "syncLabels": true,
      "labelPrefixes": ["type:", "priority:", "test:"],
      "syncMilestone": true,
      "syncAssignees": true,
      "assignAuthorWhenTaskUnassigned": true,
      "linkSubissues": true,
      "syncProject": true,
      "skipPromotionPullRequests": true,
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

Esse bloco deixa de ser exemplo de design e passa a ser contrato de implementação.

## Autenticação e permissões

Sincronizações restritas ao repositório usam `${{ github.token }}` com permissões mínimas.

Projects v2 preserva a fronteira explícita já usada pelo GPA:

```text
PROJECT_SETUP_PAT
```

O PAT nunca deve aparecer em logs ou comentários.

O workflow solicita somente:

```yaml
permissions:
  contents: read
  issues: write
```

Labels, assignees, milestone e comentários de PR são tratados pelos endpoints de issues, pois PRs são recursos baseados em issues no GitHub.

## Modelo de segurança

PR Sync segue o hardening recente do repositório:

- automação privilegiada usa `pull_request_target` / `workflow_run` confiável;
- checkout aponta para commit/branch da base confiável;
- `persist-credentials` fica desabilitado;
- forks são bloqueados no workflow e novamente na implementação;
- nenhum código do head não confiável roda com permissões de escrita;
- mutações GitHub não são repetidas automaticamente após falhas de transporte;
- falhas opcionais de permissão no Project são expostas claramente.

A distinção entre repositório-fonte e instalação embarcada descrita em `project-setup-shared-tool.md` continua válida ao distribuir o workflow.

## Idempotência

Execuções repetidas não devem duplicar:

- labels já presentes;
- assignees já presentes;
- membership do Project para task já adicionada;
- relação pai/sub-issue existente;
- comentário marcado da PR Sync.

Milestone e Status do Project convergem para o estado configurado.

## Instalação

`.github/workflows/pr-sync.yml` faz parte do manifest core do instalador. Como módulos `project_setup/*.py` são distribuídos automaticamente, `project_setup/pr_sync.py` acompanha o workflow.

Arquivos já existentes no target continuam protegidos pelo comportamento preserve-by-default do instalador.

## Validação

`tests/test_pr_sync.py` cobre:

- parsing de closing reference;
- parsing da referência de pai gerada;
- mapeamento do ciclo de vida;
- overrides de configuração;
- sincronização de labels/milestone/assignees;
- fallback de autor para task sem assignee;
- idempotência de pai/sub-issue;
- segurança para forks;
- skip de PR de promoção;
- task ausente/inválida;
- idempotência do comentário sticky;
- checkout confiável e dependência do workflow;
- distribuição do workflow pelo instalador.

Validação live de Project v2 continua pertencendo ao sandbox de Q.A, nunca ao repositório-fonte.

## Limites conhecidos

- PR Sync adiciona labels configuradas da task, mas não remove labels antigas do PR.
- Sincronização de assignee pertence ao PR Sync; solicitação de reviewers permanece responsabilidade de Guardrails/review-policy.
- Project v2 é opcional quando PAT/Project number não estiverem configurados.
- Sincronização de task em PRs de promoção fica desabilitada por padrão.

## Nomenclatura

O nome genérico da funcionalidade e do workflow é **PR Sync**.

Não introduzir `PR Hygiene` em novos códigos, workflows, nomes de configuração/CLI ou documentação do GPA, exceto em referências históricas à implementação avaliada no Take Your Pills.
