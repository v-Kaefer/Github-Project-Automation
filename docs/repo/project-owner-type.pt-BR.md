# Tipo de proprietário do GitHub Projects v2

O `project_setup` suporta GitHub Projects v2 pertencentes tanto a uma conta pessoal do GitHub quanto a uma GitHub Organization.

## Opção de setup

Quando o Project v2 será utilizado, configure o tipo do proprietário uma vez no `.env`:

```dotenv
# Conta pessoal do GitHub
PROJECT_SETUP_OWNER_TYPE=user
```

ou:

```dotenv
# Empresa/equipe representada por uma GitHub Organization
PROJECT_SETUP_OWNER_TYPE=organization
```

Os valores documentados são `user` e `organization`. A implementação também aceita `org` e `company` como aliases de `organization`.

Essa configuração não é secreta. Ela informa à camada GraphQL em qual namespace do GitHub o Project v2 pertence. Ela não altera permissões do repositório e não substitui `PROJECT_SETUP_PAT`.

## Qual valor escolher?

Use `user` quando o owner do repositório for uma conta pessoal do GitHub e o Project v2 pertencer a essa conta.

Use `organization` quando o repositório pertencer a uma empresa/equipe representada por uma GitHub Organization e o Project v2 pertencer a essa Organization.

Exemplos:

```dotenv
GITHUB_REPOSITORY=v-Kaefer/exemplo
PROJECT_SETUP_OWNER_TYPE=user
```

```dotenv
GITHUB_REPOSITORY=Empresa-Exemplo/exemplo
PROJECT_SETUP_OWNER_TYPE=organization
```

## Detecção automática

`PROJECT_SETUP_OWNER_TYPE` pode ficar vazio. Durante uma operação autenticada de Project v2, o `project_setup` consulta primeiro os metadados do owner no GitHub e resolve se ele é `User` ou `Organization` antes de montar a query GraphQL do Project.

A configuração explícita é recomendada para automações previsíveis, enquanto a autodetecção mantém compatibilidade com instalações antigas que ainda não possuem essa variável.

## Comportamento no Makefile

Os comandos normais herdam automaticamente o valor do `.env`:

```bash
make setup
make project-create
make project-sync
```

Um override pontual pode ser feito sem editar o `.env`:

```bash
make setup OWNER_TYPE=organization
make project-create OWNER_TYPE=user
```

O Makefile exporta o valor resolvido como `PROJECT_SETUP_OWNER_TYPE`, garantindo que a CLI Python e a implementação do Project v2 usem a mesma seleção.

`make help` mostra o valor resolvido. Quando ele estiver vazio, a saída informa `auto-detect`.

## Autenticação

Tipo do owner e autenticação são configurações separadas. Operações reais de Project v2 continuam exigindo:

```dotenv
PROJECT_SETUP_PAT=...
```

Para a implementação atual, utilize uma PAT classic com os escopos `repo` e `project`. Nunca versione o token.

## Por que essa opção existe?

O GraphQL do GitHub expõe Projects v2 em campos diferentes para pessoas e organizações: `user(...)` e `organization(...)`. Consultar os dois para o mesmo login pode produzir erro GraphQL quando o login existe somente em um dos namespaces.

Por isso, o `project_setup` resolve primeiro o tipo do owner e consulta apenas o namespace correspondente. Esse comportamento vale para criação, busca, sincronização, validação de Q.A e cleanup de Project v2.

## Cobertura de Q.A

A suíte de testes valida:

- seleção explícita de `user`;
- seleção explícita de `organization`;
- detecção automática de User;
- detecção automática de Organization;
- precedência da configuração do ambiente sobre a autodetecção;
- reutilização do tipo resolvido no sandbox live durante create, lookup, sync e cleanup.
