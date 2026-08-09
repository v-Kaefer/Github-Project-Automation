# Política de Validação Q.A

## Fluxo de promoção

O fluxo de release é linear:

```text
branch de implementação -> develop -> Q.A -> main
```

- branches de implementação são integradas em `develop`;
- somente `develop` pode abrir promoção para `Q.A`;
- somente `Q.A` pode abrir promoção para `main`;
- `main` não deve receber feature ou hotfix diretamente enquanto esta política estiver ativa.

As restrições são aplicadas por:

- `.github/workflows/qa-source-branch.yml`;
- `.github/workflows/main-source-branch.yml`;
- `project_setup.pr_validation.validate_branch`.

## Gate Q.A 1: validação determinística

`.github/workflows/qa-validation.yml` roda em PRs e pushes destinados à branch `Q.A`.

Ele valida:

- `make check` completo em Ubuntu / Python 3.11;
- Python 3.11, 3.12, 3.13 e 3.14 em Ubuntu;
- Python 3.11 e 3.14 em Windows;
- Python 3.11 e 3.14 em macOS;
- GNU Make no runner Windows;
- instalação do pacote e `pip check`;
- todos os entrypoints documentados da CLI;
- testes black-box de instalação e dry-run;
- resolução do `.env` pelo Makefile e overrides pela linha de comando;
- `make doctor` em modo somente leitura;
- build de wheel e source distribution;
- instalação do wheel em ambiente virtual limpo.

Esse workflow não exige credenciais de escrita no GitHub.

## Gate Q.A 2: validação live em sandbox

`.github/workflows/qa-live.yml` roda após push em `Q.A` e também pode ser disparado manualmente.

Ele usa um GitHub Environment chamado `qa`.

Configure no Environment:

| Tipo | Nome | Valor |
| --- | --- | --- |
| Environment variable | `QA_REPOSITORY` | Repositório descartável dedicado em formato `owner/repository` |
| Environment secret | `QA_PROJECT_SETUP_PAT` | PAT com as permissões de repositório e Project v2 necessárias pela implementação atual |

O workflow mapeia `QA_PROJECT_SETUP_PAT` para `PROJECT_SETUP_PAT` somente dentro do job live. O valor do secret nunca é impresso.

O repositório principal da ferramenta nunca pode ser usado como `QA_REPOSITORY`; workflow e script recusam essa configuração.

### Recursos live testados

Cada run cria recursos temporários com nomes únicos:

- uma label;
- um milestone;
- um Project v2 com fields customizados.

Para labels e milestones o fluxo é: criar -> verificar -> atualizar -> verificar -> sincronizar novamente -> confirmar que continua existindo apenas um recurso.

Para Project v2, o teste cria o Project, sincroniza duas vezes, confirma que os fields não foram duplicados e relê o estado remoto.

Antes de terminar, o workflow remove label, milestone e Project temporários. Falha no cleanup faz o job falhar.

## Teste manual de geração de issues

A geração de issues ainda não é idempotente e issues do GitHub normalmente não podem ser excluídas. Por isso ela não participa do gate automático.

`.github/workflows/qa-issue-generation.yml` é somente manual e exige a confirmação exata:

```text
RUN_NON_IDEMPOTENT_TEST
```

O workflow cria uma story e uma task com nomes únicos no sandbox, verifica a referência ao parent, fecha ambas como `not_planned` e restaura quaisquer labels alteradas ou criadas temporariamente.

As duas issues fechadas permanecem no histórico do sandbox por decisão consciente.

## Checks recomendados como obrigatórios

Para PRs destinados a `Q.A`, exigir pelo menos:

- `validate-qa-source`;
- `repository-quality / ubuntu / py3.11`;
- todos os resultados `compatibility / ...` da matriz;
- `package-artifact / wheel-and-sdist`.

Depois que o Environment `qa` estiver configurado e estabilizado, exigir também o live sandbox antes da promoção de `Q.A` para `main`.

Para PRs destinados a `main`, exigir:

- `validate-main-source`;
- checks normais do repositório e metadados de PR;
- evidência de que exatamente o commit promovido em Q.A passou pelos gates determinístico e live.

## Política de falha

Falha em Q.A bloqueia promoção. A correção volta para branch de implementação ou `develop`; não faça patch direto em `Q.A` salvo mudança explícita da política.
