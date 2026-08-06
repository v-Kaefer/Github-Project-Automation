[![Repository quality](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml/badge.svg?branch=develop)](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/v-Kaefer/Github-Project-Automation)

# GitHub Project Setup

<a id="english"></a>

`project_setup` is a self-contained toolkit for installing and operating GitHub repository automation. It provides a Makefile and Python CLI for repository discovery, configuration validation, labels, milestones, issues, sub-issues, pull-request guardrails, and GitHub Projects v2.

[Go directly to setup](#setup) · [Leia em português](#português)

## What it installs

The `core` profile can install:

- a Makefile for manual operation;
- `.env.example` for local credentials and defaults;
- the embedded `project_setup` Python package;
- GitHub Actions for repository setup, PR validation, auto-labeling, and quality checks;
- issue forms and a pull-request template;
- JSON manifests for labels, milestones, backlog items, and Project v2;
- validation scripts with actionable error messages.

Existing files are preserved unless `FORCE=1` or `--force` is explicitly used.

<a id="setup"></a>

## Setup

### 1. Requirements

- Python 3.11 or newer;
- Git;
- GNU Make for the Makefile interface;
- a GitHub account with permission to modify the target repository;
- a personal access token only when creating or synchronizing GitHub Projects v2.

The Python CLI remains available on systems without Make:

```bash
python -m project_setup --help
```

### 2. Clone and validate the tool

```bash
git clone https://github.com/v-Kaefer/Github-Project-Automation.git
cd Github-Project-Automation
git switch develop
make check
```

`make check` performs three local stages:

1. validates required files, committed artifacts, JSON, and package metadata;
2. compiles the Python sources;
3. runs unit tests.

It does not call the GitHub API and does not modify a repository. Local `__pycache__` files created during compilation are removed automatically. The quality check only rejects generated Python artifacts that are actually committed to Git. Every reported problem includes a `Fix:` instruction.

### 3. Create the local `.env`

Copy the template:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

At minimum, set the target repository:

```dotenv
GITHUB_REPOSITORY=owner/repository
```

The CLI loads `.env` automatically from the current working directory. Existing process environment variables take precedence over values in `.env`.

Run the read-only local diagnostic:

```bash
make doctor
```

`make doctor` checks the `.env`, `project_setup.json`, and referenced manifest files. It explains missing values and does not make GitHub API changes.

### 4. Authentication model

#### Repository-scoped operations

GitHub Actions automatically provides `github.token`. The workflows expose it to the Python process as:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

No custom secret named `GITHUB_TOKEN` is required. The standard repository token is used for operations such as:

- labels;
- milestones;
- issues and tasks;
- sub-issues in the same repository;
- PR validation comments;
- inferred labels.

#### GitHub Projects v2

GitHub's repository-scoped token cannot access Projects v2. Live Project v2 creation or synchronization requires `PROJECT_SETUP_PAT`.

For the current GraphQL implementation, create a **personal access token (classic)**:

1. Click your GitHub profile picture.
2. Open **Settings**.
3. Open **Developer settings**.
4. Open **Personal access tokens**.
5. Open **Tokens (classic)**.
6. Click **Generate new token** and then **Generate new token (classic)**.
7. Set a descriptive name and an expiration date.
8. Select these scopes:
   - `repo`;
   - `project`.
9. Generate the token and copy it immediately.

Official references:

- [Managing personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Automating Projects using Actions](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions)

For local execution, save it only in `.env`:

```dotenv
PROJECT_SETUP_PAT=ghp_your_token_here
```

Never commit `.env`. The repository ignores `.env` and permits only `.env.example` to be versioned.

For GitHub Actions, create a repository secret:

1. Open the target repository.
2. Open **Settings**.
3. Open **Secrets and variables** → **Actions**.
4. Select **New repository secret**.
5. Use the name `PROJECT_SETUP_PAT`.
6. Paste the token and save it.

When a live workflow requests Project v2 without this secret, it stops before applying changes and prints the exact setup path and required scopes.

> GitHub recommends a GitHub App for long-lived organization automation. The PAT path is retained here as the simplest supported setup for individual users and initial adoption.

### 5. Inspect a target repository

```bash
make discover TARGET=../my-project REPO=owner/my-project
```

The command detects common Python, Node.js, Go, Java, Rust, and .NET markers and prints the recommended setup command.

### 6. Preview installation

```bash
make init-dry TARGET=../my-project PROFILE=core
```

Install the files after reviewing the preview:

```bash
make init TARGET=../my-project PROFILE=core
```

The installer includes `Makefile` and `.env.example`. If the target already has either file, it is preserved and the installer asks you to review and merge the templates manually.

Optional Godot profile:

```bash
make init TARGET=../my-game PROFILE=godot
```

### 7. Customize the target configuration

Review at least:

- `.env.example` and the local `.env`;
- `project_setup.json`;
- `config/project/labels.json`;
- `config/project/milestones.json`;
- `config/project/project-definition.json`;
- `config/stories/backlog-manifest.json`;
- `.github/workflows/project-setup.yml`;
- `.github/workflows/main-source-branch.yml`;
- `.github/pull_request_template.md`.

Project creation and issue generation are disabled by default.

### 8. Diagnose and plan

From the target repository:

```bash
make doctor
make plan REPO=owner/repository
```

Or from this tool repository:

```bash
make doctor CONFIG=project_setup.json
make plan TARGET=../my-project REPO=owner/repository
```

`make plan` uses dry-run mode. Review the complete output before applying changes.

### 9. Apply

Repository resources without Project v2 can use a standard authenticated GitHub CLI session or another supported token:

```bash
make apply TARGET=../my-project REPO=owner/repository
```

Project v2 operations require `PROJECT_SETUP_PAT` in the target `.env`:

```bash
make project-create TARGET=../my-project REPO=owner/repository
make project-sync TARGET=../my-project REPO=owner/repository PROJECT_NUMBER=1
```

### 10. Manual GitHub Actions execution

After installation, open the target repository and select:

**Actions** → **Project setup** → **Run workflow**

The workflow defaults to dry-run. Labels, milestones, issue generation, and Project v2 creation are separate inputs. Live Project v2 creation requires the `PROJECT_SETUP_PAT` Actions secret described above.

## Makefile reference

| Target | Purpose |
| --- | --- |
| `make help` | Show the local setup sequence and available commands. |
| `make check` | Validate committed files, compile sources, and run tests. |
| `make doctor` | Inspect `.env` and local configuration without API writes. |
| `make discover TARGET=... REPO=...` | Detect the target stack and recommend setup options. |
| `make init-dry TARGET=...` | Preview files that would be installed. |
| `make init TARGET=...` | Install missing files while preserving existing files. |
| `make plan TARGET=... REPO=...` | Preview configured GitHub changes. |
| `make apply TARGET=... REPO=...` | Apply configured GitHub changes. |
| `make setup TARGET=... REPO=...` | Install files and run a dry-run. |
| `make setup-live TARGET=... REPO=...` | Install files and perform a live apply. |
| `make clean` | Remove local Python and build artifacts. |

## Safety model

- Dry-run is the default.
- Issue generation is disabled by default.
- Project creation is disabled by default.
- Existing target files are preserved.
- Project v2 uses an explicit PAT instead of silently falling back to `github.token`.
- PR workflows execute trusted code from the base commit.
- Untrusted branch names are passed through environment variables rather than interpolated into shell scripts.
- Workflow permissions are limited to the resources each workflow uses.
- Tokens are never printed by `doctor` or workflow diagnostics.

## Current limitations

- Issue generation is not yet idempotent; inspect existing issues before repeating it.
- Project v2 views listed in the definition still require manual configuration.
- GitHub rulesets and branch protection are not created automatically yet.
- The installer embeds the package in each target repository rather than using a published PyPI release.
- A summarized `make preview` with limited example output is planned but is not implemented yet.

---

<a id="português"></a>

# Configuração de Projetos no GitHub

O `project_setup` é uma ferramenta autocontida para instalar e operar automações de repositórios no GitHub. Ela oferece Makefile e CLI Python para descoberta do projeto, validação de configuração, labels, milestones, issues, sub-issues, regras de pull request e GitHub Projects v2.

[Ir diretamente para a configuração](#configuração) · [Read in English](#english)

## O que é instalado

O perfil `core` pode instalar:

- Makefile para execução manual;
- `.env.example` para credenciais e configurações locais;
- pacote Python `project_setup` incorporado;
- GitHub Actions para setup, validação de PR, auto-label e qualidade;
- formulários de issues e template de pull request;
- manifests JSON para labels, milestones, backlog e Project v2;
- scripts de validação com mensagens de correção acionáveis.

Arquivos existentes são preservados, exceto quando `FORCE=1` ou `--force` é usado explicitamente.

<a id="configuração"></a>

## Configuração

### 1. Requisitos

- Python 3.11 ou superior;
- Git;
- GNU Make para usar a interface Makefile;
- conta GitHub com permissão para modificar o repositório-alvo;
- personal access token somente para criar ou sincronizar GitHub Projects v2.

Em sistemas sem Make, use diretamente:

```bash
python -m project_setup --help
```

### 2. Clonar e validar a ferramenta

```bash
git clone https://github.com/v-Kaefer/Github-Project-Automation.git
cd Github-Project-Automation
git switch develop
make check
```

O `make check` executa três etapas locais:

1. valida arquivos obrigatórios, artefatos commitados, JSON e metadados do pacote;
2. compila os fontes Python;
3. executa os testes unitários.

Ele não chama a API do GitHub e não modifica repositórios. Os `__pycache__` locais criados durante a compilação são removidos automaticamente. O validador rejeita apenas artefatos Python realmente commitados. Cada erro apresenta uma instrução `Fix:`.

### 3. Criar o `.env` local

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux, macOS, Git Bash ou WSL:

```bash
cp .env.example .env
```

Defina ao menos o repositório-alvo:

```dotenv
GITHUB_REPOSITORY=owner/repository
```

A CLI carrega automaticamente o `.env` do diretório atual. Variáveis já definidas no processo têm prioridade sobre o arquivo.

Execute o diagnóstico local somente leitura:

```bash
make doctor
```

O `make doctor` verifica `.env`, `project_setup.json` e os manifests referenciados. Ele informa exatamente o que está ausente e não altera o GitHub.

### 4. Modelo de autenticação

#### Operações do próprio repositório

O GitHub Actions fornece automaticamente `github.token`. Os workflows o disponibilizam ao Python como:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

Não é necessário criar um secret chamado `GITHUB_TOKEN`. O token padrão atende operações como:

- labels;
- milestones;
- issues e tasks;
- sub-issues no mesmo repositório;
- comentários de validação em PRs;
- labels inferidas.

#### GitHub Projects v2

O token padrão do repositório não acessa Projects v2. A criação ou sincronização real exige `PROJECT_SETUP_PAT`.

Para a implementação GraphQL atual, crie um **personal access token (classic)**:

1. Clique na sua foto de perfil no GitHub.
2. Abra **Settings**.
3. Abra **Developer settings**.
4. Abra **Personal access tokens**.
5. Abra **Tokens (classic)**.
6. Clique em **Generate new token** e depois **Generate new token (classic)**.
7. Defina nome descritivo e validade.
8. Marque os escopos:
   - `repo`;
   - `project`.
9. Gere o token e copie imediatamente.

Documentação oficial:

- [Gerenciar personal access tokens](https://docs.github.com/pt/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Automatizar Projects usando Actions](https://docs.github.com/pt/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions)

Para uso local, salve somente no `.env`:

```dotenv
PROJECT_SETUP_PAT=ghp_seu_token_aqui
```

Nunca versione o `.env`. O repositório ignora `.env` e permite apenas `.env.example`.

Para GitHub Actions, crie um secret no repositório:

1. Abra o repositório-alvo.
2. Abra **Settings**.
3. Abra **Secrets and variables** → **Actions**.
4. Selecione **New repository secret**.
5. Use o nome `PROJECT_SETUP_PAT`.
6. Cole o token e salve.

Quando uma execução real solicitar Project v2 sem esse secret, o workflow para antes de aplicar alterações e mostra o caminho e os escopos necessários.

> Para automações permanentes em organizações, o GitHub recomenda uma GitHub App. A PAT permanece como o caminho mais simples para usuários individuais e validação inicial.

### 5. Inspecionar o repositório-alvo

```bash
make discover TARGET=../meu-projeto REPO=owner/meu-projeto
```

O comando detecta marcadores comuns de Python, Node.js, Go, Java, Rust e .NET e imprime o comando recomendado.

### 6. Simular e instalar

```bash
make init-dry TARGET=../meu-projeto PROFILE=core
make init TARGET=../meu-projeto PROFILE=core
```

O instalador inclui `Makefile` e `.env.example`. Caso o alvo já possua algum deles, o arquivo existente é preservado e a saída orienta uma mesclagem manual.

Perfil Godot opcional:

```bash
make init TARGET=../meu-jogo PROFILE=godot
```

### 7. Personalizar

Revise pelo menos:

- `.env.example` e o `.env` local;
- `project_setup.json`;
- `config/project/labels.json`;
- `config/project/milestones.json`;
- `config/project/project-definition.json`;
- `config/stories/backlog-manifest.json`;
- `.github/workflows/project-setup.yml`;
- `.github/workflows/main-source-branch.yml`;
- `.github/pull_request_template.md`.

A criação de Project e a geração de issues permanecem desativadas por padrão.

### 8. Diagnosticar e planejar

```bash
make doctor
make plan TARGET=../meu-projeto REPO=owner/repositorio
```

O `make plan` usa dry-run. Revise toda a saída antes de aplicar.

### 9. Aplicar

Para recursos do repositório sem Project v2:

```bash
make apply TARGET=../meu-projeto REPO=owner/repositorio
```

Para Project v2, configure `PROJECT_SETUP_PAT` no `.env` do alvo:

```bash
make project-create TARGET=../meu-projeto REPO=owner/repositorio
make project-sync TARGET=../meu-projeto REPO=owner/repositorio PROJECT_NUMBER=1
```

### 10. Execução manual no GitHub Actions

No repositório-alvo, abra:

**Actions** → **Project setup** → **Run workflow**

O workflow inicia em dry-run. Labels, milestones, geração de issues e criação de Project v2 são opções separadas. A criação real do Project v2 exige o secret `PROJECT_SETUP_PAT`.

## Referência do Makefile

| Alvo | Finalidade |
| --- | --- |
| `make help` | Mostrar a sequência inicial e os comandos. |
| `make check` | Validar arquivos commitados, compilar e testar. |
| `make doctor` | Verificar `.env` e configuração local sem alterar a API. |
| `make discover TARGET=... REPO=...` | Detectar a stack e recomendar opções. |
| `make init-dry TARGET=...` | Simular os arquivos que seriam instalados. |
| `make init TARGET=...` | Instalar arquivos ausentes preservando os existentes. |
| `make plan TARGET=... REPO=...` | Simular alterações configuradas no GitHub. |
| `make apply TARGET=... REPO=...` | Aplicar alterações configuradas. |
| `make setup TARGET=... REPO=...` | Instalar e executar dry-run. |
| `make setup-live TARGET=... REPO=...` | Instalar e executar alterações reais. |
| `make clean` | Remover caches Python e artefatos locais. |

## Modelo de segurança

- Dry-run é o padrão.
- Geração de issues e criação de Project ficam desativadas inicialmente.
- Arquivos existentes são preservados.
- Project v2 exige PAT explícita e não usa fallback silencioso para `github.token`.
- Workflows de PR executam código confiável da branch-base.
- Nomes de branches não são interpolados diretamente em scripts shell.
- Permissões dos workflows são limitadas às funções utilizadas.
- Tokens nunca são exibidos pelo `doctor` ou pelos logs de diagnóstico.

## Limitações atuais

- A geração de issues ainda não é idempotente.
- Views de Project v2 continuam com configuração manual.
- Rulesets e branch protection ainda não são criados automaticamente.
- O instalador incorpora o pacote no repositório-alvo em vez de usar uma versão publicada no PyPI.
- Um `make preview` resumido, com limite de exemplos, está planejado, mas ainda não foi implementado.
