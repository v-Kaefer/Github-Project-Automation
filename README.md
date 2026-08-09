[![Repository quality](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml/badge.svg?branch=develop)](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/v-Kaefer/Github-Project-Automation)

# GitHub Project Setup

<a id="english"></a>

`project_setup` is a self-contained toolkit for installing and operating GitHub repository automation. It provides a Makefile and Python CLI for labels, milestones, issues, sub-issues, pull-request guardrails, repository discovery, and GitHub Projects v2.

[Go directly to setup](#setup) · [Leia em português](#português)

## Main capabilities

- Manual operation through Make targets.
- Safe dry-run defaults for every mutating CLI command.
- Explicit `--live` or `LIVE=1` confirmation before writes.
- Guided repository discovery through the Python CLI.
- Embedded workflows, templates, manifests, and validation scripts.
- Native Windows detection in the Makefile.
- Local `.env` loading without external dependencies.
- Standard `github.token` for repository-scoped Actions operations.
- Explicit `PROJECT_SETUP_PAT` requirement for GitHub Projects v2.
- Actionable diagnostics with a `Fix:` instruction for validation errors.

<a id="setup"></a>

## Setup

### 1. Requirements

- Python 3.11 or newer;
- Git;
- GNU Make for the Makefile interface;
- permission to modify the target GitHub repository;
- a personal access token only for live GitHub Projects v2 operations.

The Makefile detects `OS=Windows_NT`. It uses `python` on Windows and `python3` on Linux, macOS, Git Bash, and WSL. The command can still be overridden:

```powershell
make PYTHON=py check
```

The Python CLI can be used without Make:

```bash
python -m project_setup --help
```

### 2. Validate the tool

```bash
make check
```

The command runs three local stages:

1. validate required and committed files, JSON, script references, and package metadata;
2. compile Python sources;
3. run unit tests.

It does not call the GitHub API. Local `__pycache__` files are removed automatically and are not reported as committed files. A generated artifact only fails the check when `git ls-files` confirms it is tracked.

Typical corrective output:

```text
ERROR: Generated Python artifact is committed: project_setup/__pycache__/module.pyc
  Fix: Run `git rm --cached -- project_setup/__pycache__/module.pyc` and then `make clean`.
```

### 3. Create the local environment

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux, macOS, Git Bash, or WSL:

```bash
cp .env.example .env
```

Set the repository:

```dotenv
GITHUB_REPOSITORY=owner/repository
```

The CLI loads `.env` automatically from the current working directory. Existing process environment variables take precedence.

Run the read-only diagnostic:

```bash
make doctor
```

`make doctor` reports the operating system, Python executable, `.env`, configuration files, token source, GitHub CLI installation, and `gh auth` status. It never prints token values and does not write to GitHub.

### 4. Authentication

#### Repository-scoped GitHub Actions operations

GitHub automatically creates `github.token` for each job. The workflows expose it to Python as:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

Do not create a custom secret named `GITHUB_TOKEN`. The standard token is used for operations inside the repository, subject to the workflow `permissions` block:

- labels;
- milestones;
- issues and tasks;
- sub-issues in the same repository;
- PR validation comments;
- inferred labels.

#### Local GitHub CLI authentication

The CLI can fall back to an authenticated GitHub CLI session:

```bash
gh auth login
gh auth status
```

`make doctor` distinguishes a missing CLI, valid authentication, invalid authentication, and environment-token authentication. An invalid `gh` session does not block execution when a valid token is available in `.env`.

#### GitHub Projects v2

The repository-scoped token cannot access Projects v2. Live Project creation and synchronization require `PROJECT_SETUP_PAT`.

For the current GraphQL implementation, create a **personal access token (classic)**:

1. Click your GitHub profile picture.
2. Open **Settings**.
3. Open **Developer settings**.
4. Open **Personal access tokens**.
5. Open **Tokens (classic)**.
6. Select **Generate new token** → **Generate new token (classic)**.
7. Define a descriptive name and expiration.
8. Select the scopes:
   - `repo`;
   - `project`.
9. Generate the token and copy it immediately.

Official GitHub documentation:

- [Managing personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Automating Projects using Actions](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions)

For local use, save the PAT in `.env`:

```dotenv
PROJECT_SETUP_PAT=ghp_your_token_here
```

Never commit `.env`.

For the manual Actions workflow, save the PAT as a repository secret:

1. Open the target repository.
2. Open **Settings**.
3. Open **Secrets and variables** → **Actions**.
4. Select **New repository secret**.
5. Name it `PROJECT_SETUP_PAT`.
6. Paste and save the token.

A live workflow that requests Project v2 without the secret stops before applying changes and prints the required configuration path and scopes.

> GitHub recommends a GitHub App for long-lived organization automation. The PAT workflow remains the simplest initial setup for individual users.

### 5. Discover and install

Inspect a target repository:

```bash
make discover TARGET=../my-project REPO=owner/my-project
```

Non-interactive discovery always recommends a dry-run command, even when `project_setup.json` contains an old `dryRun=false` value.

Preview installed files:

```bash
make init-dry TARGET=../my-project PROFILE=core
```

The installation dry-run does not create the target directory.

Install the core automation:

```bash
make init TARGET=../my-project PROFILE=core
```

The installer includes `Makefile` and `.env.example`. Existing files are preserved. If the target already has either file, review and merge the template manually.

Combined install and remote dry-run:

```bash
make setup TARGET=../my-project REPO=owner/my-project
```

`make setup` installs missing files, then executes the configured API phase in dry-run mode. It does not write remote GitHub changes.

### 6. Customize

Review at least:

- `.env.example` and the untracked `.env`;
- `project_setup.json`;
- `config/project/labels.json`;
- `config/project/milestones.json`;
- `config/project/project-definition.json`;
- `config/stories/backlog-manifest.json`;
- `.github/workflows/project-setup.yml`;
- `.github/workflows/main-source-branch.yml`;
- `.github/pull_request_template.md`.

Issue generation and Project creation are disabled by default.

### 7. Diagnose and plan

```bash
make doctor
make plan TARGET=../my-project REPO=owner/repository
```

`make plan` is always a dry-run. Review the complete output before a live operation.

### 8. Apply the complete configured setup

`make apply` is also a dry-run unless live execution is explicitly enabled:

```bash
make apply TARGET=../my-project REPO=owner/repository
```

Apply changes only after reviewing the plan:

```bash
make apply TARGET=../my-project REPO=owner/repository LIVE=1
```

The CLI equivalent is:

```bash
python -m project_setup apply --repo owner/repository --live
```

If live Project creation is enabled, `PROJECT_SETUP_PAT` is mandatory.

### 9. Run individual modules manually

Individual Make targets are dry-run by default:

```bash
make labels TARGET=../my-project REPO=owner/repository
make milestones TARGET=../my-project REPO=owner/repository
make issues TARGET=../my-project REPO=owner/repository
make project-create TARGET=../my-project REPO=owner/repository
make project-sync TARGET=../my-project REPO=owner/repository PROJECT_NUMBER=1
```

After reviewing the output, add `LIVE=1` explicitly:

```bash
make labels TARGET=../my-project REPO=owner/repository LIVE=1
make milestones TARGET=../my-project REPO=owner/repository LIVE=1
make issues TARGET=../my-project REPO=owner/repository LIVE=1
make project-create TARGET=../my-project REPO=owner/repository LIVE=1
make project-sync TARGET=../my-project REPO=owner/repository PROJECT_NUMBER=1 LIVE=1
```

Project v2 live commands require `PROJECT_SETUP_PAT` in the target `.env`.

Without a PAT, `project-sync` dry-run produces an offline preview of the local Project definition and clearly states that remote fields, items, and issues were not queried.

### 10. Run manually in GitHub Actions

In the target repository:

**Actions** → **Project setup** → **Run workflow**

The workflow defaults to dry-run. Labels, milestones, issue generation, and Project creation are separate inputs. A live Project v2 run requires the `PROJECT_SETUP_PAT` Actions secret.

## Makefile reference

| Target | Purpose |
| --- | --- |
| `make help` | Show detected platform, setup steps, and commands. |
| `make check` | Validate committed files, compile, and test. |
| `make doctor` | Inspect OS, `.env`, tokens, `gh auth`, and configuration without API writes. |
| `make discover TARGET=... REPO=...` | Detect the target stack and recommend safe setup options. |
| `make init-dry TARGET=...` | Preview installed files without creating the target directory. |
| `make init TARGET=...` | Install missing files while preserving existing files. |
| `make setup TARGET=... REPO=...` | Install missing files and run the configured remote phase in dry-run mode. |
| `make plan TARGET=... REPO=...` | Preview the complete configured API phase. |
| `make apply TARGET=... REPO=...` | Preview the configured API phase; dry-run remains the default. |
| `make apply TARGET=... REPO=... LIVE=1` | Apply the complete configured API phase explicitly. |
| `make <module> ...` | Preview one module. |
| `make <module> ... LIVE=1` | Apply one module explicitly. |
| `make clean` | Remove local Python and build artifacts. |

## Security model

- Dry-run is the default for all mutating CLI commands.
- Existing target files are preserved.
- Installation dry-runs do not create directories.
- Project v2 never silently falls back to `github.token`.
- GitHub HTTP requests have a finite timeout.
- Automatic retries are limited to idempotent read requests; mutations are not replayed after transport failures.
- Workflows use minimum repository permissions.
- Privileged `pull_request_target` workflows check out trusted base-branch automation.
- Read-only `pull_request` test workflows may test the proposed PR content.
- Untrusted branch names are passed through environment variables, not interpolated into shell source.
- Tokens are never printed by diagnostics.

## Current limitations

- Issue generation is not idempotent yet and must not be repeated without reviewing existing issues.
- Project v2 views remain a manual configuration step.
- Rulesets and branch protection are not created automatically.
- The package is embedded in target repositories instead of being installed from PyPI.
- Milestone synchronization intentionally inspects at most the first 100 existing milestones.
- A summarized `make preview` with a configurable example limit is planned but not implemented yet.

---

<a id="português"></a>

# Configuração de Projetos no GitHub

O `project_setup` é uma ferramenta autocontida para instalar e operar automações de repositórios no GitHub. Ela oferece Makefile e CLI Python para labels, milestones, issues, sub-issues, validações de pull request, descoberta do repositório e GitHub Projects v2.

[Ir diretamente para a configuração](#configuração) · [Read in English](#english)

## Principais recursos

- Execução manual por Makefile.
- Dry-run seguro em todos os comandos mutáveis.
- Confirmação explícita por `--live` ou `LIVE=1` antes de qualquer escrita.
- Descoberta guiada pela CLI Python.
- Workflows, templates, manifests e validadores incorporados.
- Identificação nativa do Windows pelo Makefile.
- Carregamento automático de `.env`, sem dependências externas.
- `github.token` padrão para operações do próprio repositório.
- `PROJECT_SETUP_PAT` explícita para GitHub Projects v2.
- Erros com instruções `Fix:`.

<a id="configuração"></a>

## Configuração

### 1. Requisitos

- Python 3.11 ou superior;
- Git;
- GNU Make para usar o Makefile;
- permissão para modificar o repositório-alvo;
- personal access token somente para operações reais de Project v2.

O Makefile detecta `OS=Windows_NT`. No Windows, usa `python`; em Linux, macOS, Git Bash e WSL, usa `python3`. É possível sobrescrever:

```powershell
make PYTHON=py check
```

Sem Make:

```bash
python -m project_setup --help
```

### 2. Validar a ferramenta

```bash
make check
```

O comando:

1. valida arquivos obrigatórios e commitados, JSON, referências de scripts e metadados do pacote;
2. compila os fontes Python;
3. executa os testes unitários.

Ele não chama a API do GitHub. Os `__pycache__` locais são removidos automaticamente e não são confundidos com arquivos versionados. Um artefato gerado somente causa falha quando `git ls-files` confirma que ele está commitado.

### 3. Criar o ambiente local

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux, macOS, Git Bash ou WSL:

```bash
cp .env.example .env
```

Defina o repositório:

```dotenv
GITHUB_REPOSITORY=owner/repositorio
```

A CLI carrega automaticamente o `.env` do diretório atual. Variáveis já presentes no processo têm prioridade.

Execute:

```bash
make doctor
```

O `doctor` informa sistema operacional, executável Python, `.env`, configuração, origem do token, instalação da GitHub CLI e situação do `gh auth`. Ele não exibe tokens e não altera o GitHub.

### 4. Autenticação

#### Operações do repositório no Actions

O GitHub fornece automaticamente `github.token`. Os workflows o passam ao Python assim:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

Não crie um secret personalizado chamado `GITHUB_TOKEN`. O token padrão atende, conforme o bloco `permissions`:

- labels;
- milestones;
- issues e tasks;
- sub-issues no mesmo repositório;
- comentários de validação em PRs;
- labels inferidas.

#### Autenticação local da GitHub CLI

```bash
gh auth login
gh auth status
```

O `make doctor` diferencia CLI ausente, autenticação válida, autenticação inválida e tokens definidos no ambiente. Um `gh auth` inválido não bloqueia o uso quando existe outro token válido no `.env`.

#### GitHub Projects v2

O token padrão do repositório não acessa Projects v2. Criação e sincronização reais exigem `PROJECT_SETUP_PAT`.

Para a implementação GraphQL atual, crie um **personal access token classic**:

1. clique na foto de perfil;
2. abra **Settings**;
3. abra **Developer settings**;
4. abra **Personal access tokens**;
5. abra **Tokens (classic)**;
6. selecione **Generate new token** → **Generate new token (classic)**;
7. defina nome e validade;
8. marque os escopos `repo` e `project`;
9. gere e copie o token imediatamente.

Documentação oficial:

- [Gerenciar personal access tokens](https://docs.github.com/pt/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Automatizar Projects usando Actions](https://docs.github.com/pt/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions)

Para execução local, salve no `.env`:

```dotenv
PROJECT_SETUP_PAT=ghp_seu_token_aqui
```

Nunca versione o `.env`.

Para Actions, crie o secret:

**Repositório** → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Nome:

```text
PROJECT_SETUP_PAT
```

Uma execução real de Project v2 sem esse secret para antes de aplicar alterações e mostra o caminho e os escopos necessários.

> Para automações permanentes em organizações, o GitHub recomenda uma GitHub App. A PAT é mantida como o caminho inicial mais simples.

### 5. Descobrir e instalar

```bash
make discover TARGET=../meu-projeto REPO=owner/meu-projeto
make init-dry TARGET=../meu-projeto PROFILE=core
make init TARGET=../meu-projeto PROFILE=core
```

A descoberta não interativa sempre recomenda dry-run. O dry-run de instalação não cria o diretório-alvo.

O instalador inclui `Makefile` e `.env.example`. Arquivos existentes são preservados e devem ser mesclados manualmente.

Fluxo combinado de instalação e simulação remota:

```bash
make setup TARGET=../meu-projeto REPO=owner/meu-projeto
```

Esse comando instala arquivos ausentes e executa o plano remoto em dry-run, sem alterar a API do GitHub.

### 6. Personalizar

Revise:

- `.env.example` e o `.env` não versionado;
- `project_setup.json`;
- manifests em `config/project` e `config/stories`;
- workflows e templates em `.github/`.

Geração de issues e criação de Project ficam desativadas por padrão.

### 7. Diagnosticar e planejar

```bash
make doctor
make plan TARGET=../meu-projeto REPO=owner/repositorio
```

O `make plan` sempre usa dry-run.

### 8. Aplicar a configuração completa

Sem `LIVE=1`, o comando continua sendo uma simulação:

```bash
make apply TARGET=../meu-projeto REPO=owner/repositorio
```

A escrita exige confirmação explícita:

```bash
make apply TARGET=../meu-projeto REPO=owner/repositorio LIVE=1
```

Equivalente pela CLI:

```bash
python -m project_setup apply --repo owner/repositorio --live
```

Se a configuração habilitar criação de Project v2, `PROJECT_SETUP_PAT` será obrigatória.

### 9. Executar módulos individualmente

Dry-run padrão:

```bash
make labels TARGET=../meu-projeto REPO=owner/repositorio
make milestones TARGET=../meu-projeto REPO=owner/repositorio
make issues TARGET=../meu-projeto REPO=owner/repositorio
make project-create TARGET=../meu-projeto REPO=owner/repositorio
make project-sync TARGET=../meu-projeto REPO=owner/repositorio PROJECT_NUMBER=1
```

Após revisar, adicione `LIVE=1`:

```bash
make labels TARGET=../meu-projeto REPO=owner/repositorio LIVE=1
make milestones TARGET=../meu-projeto REPO=owner/repositorio LIVE=1
make issues TARGET=../meu-projeto REPO=owner/repositorio LIVE=1
make project-create TARGET=../meu-projeto REPO=owner/repositorio LIVE=1
make project-sync TARGET=../meu-projeto REPO=owner/repositorio PROJECT_NUMBER=1 LIVE=1
```

Os comandos reais de Project v2 exigem `PROJECT_SETUP_PAT` no `.env` do alvo.

Sem PAT, o dry-run de `project-sync` apresenta apenas a definição local e informa claramente que fields, items e issues remotos não foram consultados.

### 10. Executar manualmente no Actions

No repositório-alvo:

**Actions** → **Project setup** → **Run workflow**

O workflow inicia em dry-run. Labels, milestones, geração de issues e criação de Project são entradas separadas. Project v2 real exige o secret `PROJECT_SETUP_PAT`.

## Referência do Makefile

| Alvo | Finalidade |
| --- | --- |
| `make help` | Mostrar plataforma detectada, sequência inicial e comandos. |
| `make check` | Validar arquivos commitados, compilar e testar. |
| `make doctor` | Verificar SO, `.env`, tokens, `gh auth` e configuração sem escrita na API. |
| `make discover TARGET=... REPO=...` | Detectar a stack e recomendar opções seguras. |
| `make init-dry TARGET=...` | Simular arquivos instalados sem criar o diretório-alvo. |
| `make init TARGET=...` | Instalar arquivos ausentes preservando existentes. |
| `make setup TARGET=... REPO=...` | Instalar arquivos ausentes e executar o plano remoto em dry-run. |
| `make plan TARGET=... REPO=...` | Simular a fase completa da API. |
| `make apply TARGET=... REPO=...` | Simular a fase configurada; dry-run permanece o padrão. |
| `make apply TARGET=... REPO=... LIVE=1` | Aplicar explicitamente a fase configurada. |
| `make <módulo> ...` | Simular um módulo. |
| `make <módulo> ... LIVE=1` | Aplicar explicitamente um módulo. |
| `make clean` | Remover caches Python e artefatos locais. |

## Segurança

- Dry-run é o padrão em todos os comandos mutáveis.
- Arquivos existentes são preservados.
- Dry-run de instalação não cria diretórios.
- Project v2 não usa fallback silencioso para `github.token`.
- Chamadas HTTP possuem timeout finito.
- Retentativas automáticas ficam restritas a leituras idempotentes; mutações não são repetidas após falhas de transporte.
- Workflows usam permissões mínimas.
- Workflows privilegiados com `pull_request_target` usam automação confiável da branch-base.
- Workflows de teste somente leitura com `pull_request` podem validar o conteúdo proposto no PR.
- Nomes de branches passam por variáveis de ambiente, sem interpolação direta no shell.
- Diagnósticos nunca imprimem tokens.

## Limitações atuais

- A geração de issues ainda não é idempotente e não deve ser repetida sem revisar as issues existentes.
- Views de Project v2 continuam manuais.
- Rulesets e branch protection ainda não são criados.
- O pacote é incorporado nos repositórios-alvo, sem publicação no PyPI.
- A sincronização de milestones consulta intencionalmente no máximo os primeiros 100 milestones existentes.
- Um `make preview` resumido, com limite configurável de exemplos, está planejado, mas ainda não foi implementado.
