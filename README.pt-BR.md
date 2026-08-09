[![Repository quality](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml/badge.svg?branch=develop)](https://github.com/v-Kaefer/Github-Project-Automation/actions/workflows/repo-quality.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/v-Kaefer/Github-Project-Automation)

# GitHub Project Setup

[English](README.md) · [Início rápido](#2-início-rápido) · [Documentação](#6-documentação)

O `project_setup` é uma ferramenta autocontida para instalar e operar automações reutilizáveis em repositórios GitHub. Ela combina Makefile, CLI Python, workflows do GitHub Actions, manifests e scripts de validação para que um repositório possa ser configurado manualmente, por automação ou com auxílio de IA sem esconder o que será alterado.

O foco é configurar com segurança labels, milestones, issues, sub-issues, guardrails de pull request, descoberta de repositório e GitHub Projects v2. Comandos mutáveis usam dry-run por padrão e exigem modo live explícito antes de escrever no GitHub.

## 1. Visão geral

O GitHub Project Setup foi pensado para ser incorporado ao repositório-alvo e operado a partir dele. O pacote instalado continua legível e editável, sem depender de um serviço remoto opaco.

Usos típicos:

- instalar workflows reutilizáveis e templates de issue/PR;
- sincronizar labels e milestones a partir de manifests JSON versionados;
- gerar stories e tasks estruturadas;
- opcionalmente vincular tasks como sub-issues;
- criar e sincronizar GitHub Projects v2;
- validar metadados de pull request e convenções do repositório;
- inspecionar um projeto e recomendar um fluxo de setup antes de aplicar alterações;
- disponibilizar as mesmas operações para pessoas, scripts e agentes de IA através de comandos previsíveis em Make/CLI.

A segurança faz parte da interface: arquivos existentes no alvo são preservados por padrão, mutações de API não são repetidas automaticamente após falhas de transporte e qualquer execução real precisa ser solicitada explicitamente.

## 2. Início rápido

### Requisitos

- Python 3.11+;
- Git;
- GNU Make para usar a interface do Makefile;
- permissão de acesso ao repositório-alvo;
- `PROJECT_SETUP_PAT` somente quando forem necessárias operações reais em GitHub Projects v2.

O Makefile detecta Windows através de `OS=Windows_NT`: usa `python` por padrão no Windows e `python3` em ambientes POSIX. O executável pode ser sobrescrito, por exemplo: `make PYTHON=py check`.

### Validar a ferramenta

```bash
make doctor
make check
```

`make doctor` é somente leitura e informa ambiente local, `.env`, origem do token, estado do `gh auth` e arquivos de configuração referenciados. `make check` valida a estrutura do repositório, compila o código Python e executa os testes sem escrever no GitHub.

### Preparar a configuração local

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux, macOS, Git Bash ou WSL:

```bash
cp .env.example .env
```

No mínimo, defina o repositório quando não quiser passar `REPO=` em cada comando:

```dotenv
GITHUB_REPOSITORY=owner/repositorio
```

Para Projects v2, configure também a PAT descrita em [Autenticação](#3-autenticação).

### Inspecionar e instalar em outro repositório

```bash
make discover TARGET=../meu-projeto REPO=owner/meu-projeto
make init-dry TARGET=../meu-projeto
make setup TARGET=../meu-projeto REPO=owner/meu-projeto
```

`init-dry` mostra os arquivos que seriam instalados. `setup` instala os arquivos locais ausentes e em seguida executa a fase configurada do GitHub em dry-run; ele **não** aplica alterações remotas.

Após revisar a saída, a execução completa real é explícita:

```bash
make setup-live TARGET=../meu-projeto REPO=owner/meu-projeto
```

Para controle mais granular, use os comandos individuais em [Comandos principais](#4-comandos-principais).

## 3. Autenticação

| Uso | Credencial | Setup |
| --- | --- | --- |
| Operações do próprio repositório dentro do GitHub Actions | `${{ github.token }}` exposto como `GITHUB_TOKEN` | [Automático — sem secret personalizado](#token-automático-do-repositório) |
| Labels, milestones, issues, comentários e operações similares executadas localmente | `gh auth` válido, `GITHUB_TOKEN`, `GH_TOKEN` ou `PROJECT_SETUP_PAT` | [Manual/configurado](#autenticação-local) |
| GitHub Projects v2 localmente | `PROJECT_SETUP_PAT` no `.env` | [PAT manual/configurada](#autenticação-do-projects-v2) |
| GitHub Projects v2 pelo Actions | secret de repositório `PROJECT_SETUP_PAT` | [PAT + secret manual/configurado](#autenticação-do-projects-v2) |

### Token automático do repositório

O GitHub cria `github.token` automaticamente para cada job do Actions. Os workflows do próprio repositório o expõem ao Python assim:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

Não crie um secret personalizado `GITHUB_TOKEN` para os workflows normais. O acesso efetivo é controlado pelo bloco `permissions:` de cada workflow.

### Autenticação local

Uma execução local pode usar uma sessão autenticada da GitHub CLI:

```bash
gh auth login
gh auth status
```

ou um dos tokens suportados no ambiente/`.env`. `make doctor` informa qual origem está disponível e reporta separadamente um `gh auth` inválido sem imprimir credenciais. Uma sessão quebrada do `gh` não bloqueia a execução quando outro token válido estiver configurado.

### Autenticação do Projects v2

Criação e sincronização reais de Project v2 exigem `PROJECT_SETUP_PAT` explícita; o token padrão do repositório não é usado como fallback silencioso.

Para a implementação GraphQL atual, crie um **personal access token classic**:

1. foto do perfil no GitHub → **Settings**;
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**;
3. **Generate new token (classic)**;
4. escolha validade e marque os escopos `repo` e `project`;
5. gere e copie o token.

Para uso local:

```dotenv
PROJECT_SETUP_PAT=ghp_seu_token_aqui
```

Para Actions: **Settings** do repositório → **Secrets and variables** → **Actions** → **New repository secret** → `PROJECT_SETUP_PAT`.

Nunca versione o `.env`. Consulte a documentação do GitHub sobre [personal access tokens](https://docs.github.com/pt/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) e [automação de Projects](https://docs.github.com/pt/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions).

## 4. Comandos principais

Dry-run é o padrão para operações remotas mutáveis. Use `LIVE=1` somente depois de revisar a simulação.

| Comando | Modo padrão | O que faz |
| --- | --- | --- |
| `make help` | Somente leitura | Mostra plataforma detectada, comando Python e targets disponíveis. |
| `make doctor` | Somente leitura | Verifica `.env`, origem dos tokens, `gh auth`, SO/Python, configuração e manifests referenciados. |
| `make check` | Validação local | Executa quality checks, compilação e testes unitários. |
| `make discover TARGET=... REPO=...` | Somente leitura | Detecta a stack do alvo e imprime um comando recomendado seguro. |
| `make init-dry TARGET=...` | Dry-run | Mostra quais arquivos locais seriam instalados sem criar o diretório-alvo. |
| `make init TARGET=...` | Escrita local | Instala arquivos ausentes preservando os já existentes. |
| `make setup TARGET=... REPO=...` | Instalação local + dry-run remoto | Instala arquivos ausentes e depois simula a fase configurada da API. |
| `make plan TARGET=... REPO=...` | Dry-run | Simula a fase completa configurada da API do GitHub. |
| `make apply TARGET=... REPO=...` | Dry-run | Executa a fase configurada sem escrita. Use `LIVE=1` para aplicar. |
| `make labels REPO=...` | Dry-run | Simula sincronização de labels. |
| `make milestones REPO=...` | Dry-run | Simula sincronização de milestones. |
| `make issues REPO=...` | Dry-run | Simula geração de stories/tasks. |
| `make project-create REPO=...` | Dry-run | Simula criação de Project v2. |
| `make project-sync REPO=... PROJECT_NUMBER=1` | Dry-run | Simula sincronização de Project v2; sem PAT, usa preview offline da definição. |
| `make clean` | Escrita local | Remove apenas artefatos Python/build gerados. |

Exemplos de escrita explícita:

```bash
make labels REPO=owner/repositorio LIVE=1
make issues REPO=owner/repositorio LIVE=1
make project-create REPO=owner/repositorio LIVE=1
make apply TARGET=../meu-projeto REPO=owner/repositorio LIVE=1
```

Na CLI, o equivalente é `--live`; `--no-dry-run` permanece apenas como alias de compatibilidade.

## 5. Segurança e modelo de execução

A ferramenta é deliberadamente conservadora porque o setup mistura arquivos locais, recursos REST, recursos GraphQL e credenciais.

- **Dry-run primeiro:** todo comando remoto mutável simula por padrão. Escrita real exige `--live` ou `LIVE=1`.
- **Preservação dos arquivos do alvo:** o instalador ignora arquivos existentes salvo quando a sobrescrita é pedida explicitamente. Makefiles e templates de ambiente existentes devem ser revisados e mesclados, não substituídos cegamente.
- **Preview de instalação sem efeito colateral:** `init --dry-run` não cria o diretório-alvo.
- **Fronteira explícita de Project v2:** operações reais exigem `PROJECT_SETUP_PAT`; não existe fallback silencioso para `github.token`.
- **Sem log de credenciais:** os diagnósticos mostram origem/estado, nunca o valor dos tokens.
- **HTTP restrito:** as chamadas têm timeout finito e ficam restritas a `https://api.github.com`.
- **Proteção contra repetição de mutações:** retentativas automáticas de transporte ficam limitadas a leituras idempotentes. Uma resposta perdida após `POST`, `PATCH` ou `DELETE` não provoca replay automático.
- **Workflows privilegiados confiáveis:** workflows com `pull_request_target` executam automação da branch-base confiável. Workflows de teste somente leitura podem validar o conteúdo proposto pelo PR.
- **Entrada multiplataforma:** diferenças de SO ficam atrás das interfaces Python/Make, evitando dependência de comandos Unix-only como `test` no Windows.

Limitações intencionais atuais: geração de issues ainda não é idempotente, views do Project v2 continuam manuais, rulesets/branch protection não são criados e a sincronização de milestones consulta no máximo os primeiros 100 milestones existentes.

## 6. Documentação

| Documento | O que contém |
| --- | --- |
| [README em inglês](README.md) | Versão principal internacional com visão geral, quick start, autenticação, comandos, segurança e licença. |
| [Runbook do Project Setup](docs/repo/project-setup-runbook.pt-BR.md) | Procedimento operacional passo a passo para configurar, diagnosticar, simular, instalar e aplicar a ferramenta em outro repositório. |
| [Internos da ferramenta compartilhada](docs/repo/project-setup-shared-tool.md) | Modelo de distribuição, limites do pacote/CLI, fronteira de autenticação, decisões de segurança HTTP e escopo do core reutilizável. |
| [Política de branches](docs/repo/branching-policy.pt-BR.md) | Convenções de nomes/origens de branches e regras esperadas para pull requests. |
| [Política do Project board](docs/repo/project-board-policy.pt-BR.md) | Fields, statuses, tipos de item e convenções esperadas pelo Project v2 e pelos manifests genéricos. |
| [Contrato de referências de scripts](docs/repo/script-reference-contract.pt-BR.md) | Regra que evita scripts órfãos: todo script precisa ter chamador explícito e referência no instalador. |
| [Guia da documentação](docs/DOCUMENTATION-GUIDE.md) | Mapa entre arquivos de configuração, workflows, implementações e documentação autoritativa. |
| [Relatório do teste real](TESTE_REAL_RELATORIO.md) | Registro da primeira validação end-to-end real, incluindo criação de Project/issues e problemas de ambiente descobertos no teste. |

## 7. Licença e atribuição

O GitHub Project Setup é licenciado sob a [Apache License 2.0](LICENSE).

**Criado e originalmente desenvolvido por [v-Kaefer](https://github.com/v-Kaefer).** O repositório inclui um arquivo [`NOTICE`](NOTICE) com o aviso de atribuição do projeto. A Apache-2.0 exige que derivados distribuídos que incluam o código relevante preservem os avisos de atribuição aplicáveis desse NOTICE em forma legível.

Quando o instalador incorpora `project_setup` em outro repositório, os arquivos de licença e atribuição são instalados em `licenses/project_setup/`, permitindo que o projeto-alvo mantenha sua própria licença principal sem perder os créditos e termos aplicáveis a esta ferramenta.
