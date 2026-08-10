# Runbook — GitHub Project Setup

## Objetivo

Instalar e operar as automações em outro repositório sem sobrescrever arquivos existentes e sem executar alterações remotas antes de uma revisão.

## 1. Validar a ferramenta

```bash
make check
```

O comando:

1. valida somente arquivos commitados e configurações;
2. compila os fontes Python;
3. remove caches gerados;
4. executa os testes.

Caches locais em `__pycache__` não são tratados como arquivos versionados. Quando houver uma falha real, a saída apresenta uma instrução `Fix:`.

### Windows

O Makefile detecta `OS=Windows_NT`, usa `python` por padrão e não depende do comando Unix `test`. Em Linux, macOS, Git Bash e WSL, o padrão permanece `python3`.

A detecção pode ser conferida com:

```bash
make help
make doctor
```

O comando Python ainda pode ser sobrescrito explicitamente:

```powershell
make PYTHON=py check
```

## 2. Criar o ambiente local

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux, macOS, Git Bash ou WSL:

```bash
cp .env.example .env
```

Defina o alvo e o repositório uma vez:

```dotenv
PROJECT_SETUP_TARGET=../meu-projeto
GITHUB_REPOSITORY=owner/repositorio
PROJECT_SETUP_CONFIG=project_setup.json
PROJECT_SETUP_PROJECT_NUMBER=
```

- `PROJECT_SETUP_TARGET`: caminho local até o projeto que será configurado;
- `GITHUB_REPOSITORY`: repositório remoto no formato `owner/repository`;
- `PROJECT_SETUP_CONFIG`: arquivo principal de configuração;
- `PROJECT_SETUP_PROJECT_NUMBER`: opcional; pode ser preenchido depois que um Project v2 existir.

Se a ferramenta estiver sendo executada de dentro do próprio repositório-alvo, use:

```dotenv
PROJECT_SETUP_TARGET=.
```

No Windows, caminhos com `/` são recomendados para simplificar portabilidade, por exemplo:

```dotenv
PROJECT_SETUP_TARGET=C:/Users/nome/projeto
```

O Makefile usa o mesmo parser Python da CLI para resolver esses valores. Ele não faz `include .env` diretamente.

Valores passados explicitamente ao Make continuam tendo precedência para uma execução pontual:

```bash
make setup TARGET=../outro-projeto REPO=owner/outro-repo
```

`LIVE=1` e `FORCE=1` não são armazenados como defaults no `.env`; mutações e sobrescritas continuam decisões explícitas em cada execução.

## 3. Configurar autenticação

### Operações do repositório

No GitHub Actions, labels, milestones, issues, sub-issues e comentários usam o token padrão:

```yaml
GITHUB_TOKEN: ${{ github.token }}
```

Não crie um secret chamado `GITHUB_TOKEN`.

Para execução local sem Project v2, também é possível usar uma sessão autenticada do GitHub CLI:

```bash
gh auth login
gh auth status
```

O `make doctor` diferencia:

- GitHub CLI ausente;
- GitHub CLI instalada com autenticação válida;
- GitHub CLI instalada com autenticação inválida;
- token recebido por `GITHUB_TOKEN`, `GH_TOKEN`, `PROJECT_SETUP_PAT` ou `gh`.

Uma autenticação inválida do `gh` não bloqueia a ferramenta quando existe outro token válido no `.env`.

### GitHub Projects v2

Project v2 não pode usar o token padrão do repositório. Crie um personal access token classic:

1. foto de perfil;
2. **Settings**;
3. **Developer settings**;
4. **Personal access tokens**;
5. **Tokens (classic)**;
6. **Generate new token (classic)**;
7. selecione os escopos `repo` e `project`;
8. gere e copie o token.

Para execução local, salve no `.env`:

```dotenv
PROJECT_SETUP_PAT=ghp_seu_token
```

Para Actions, salve como secret do repositório:

**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Nome:

```text
PROJECT_SETUP_PAT
```

Uma execução real de Project v2 sem essa PAT termina antes das alterações e informa o caminho de configuração.

## 4. Executar o diagnóstico

```bash
make help
make doctor
```

`make help` mostra os defaults resolvidos pelo Makefile para alvo, repositório, configuração e Project v2.

O `doctor` verifica:

- sistema operacional e executável Python;
- presença do `.env`;
- repositório configurado;
- disponibilidade e origem da autenticação;
- estado de `gh auth`;
- presença específica de `PROJECT_SETUP_PAT`;
- validade de `project_setup.json`;
- existência dos manifests referenciados.

Nenhum dos dois aplica alterações no GitHub.

## 5. Inspecionar o repositório-alvo

Com o `.env` configurado:

```bash
make discover
```

O modo automático sempre recomenda dry-run. Para um override pontual:

```bash
make discover TARGET=../outro-projeto REPO=owner/outro-repo
```

## 6. Simular a instalação

```bash
make init-dry
```

O dry-run não cria o diretório-alvo.

## 7. Instalar os arquivos

```bash
make init
```

O instalador também leva `Makefile` e `.env.example`. Arquivos existentes são preservados e devem ser mesclados manualmente. A substituição consciente exige `FORCE=1`:

```bash
make init FORCE=1
```

### Fluxo combinado

```bash
make setup
```

Esse comando executa a instalação real dos arquivos ausentes e, em seguida, o plano remoto em dry-run. Ele não aplica alterações na API do GitHub.

## 8. Personalizar

Revise:

- `.env.example` e `.env`;
- `project_setup.json`;
- `config/project/labels.json`;
- `config/project/milestones.json`;
- `config/project/project-definition.json`;
- `config/stories/backlog-manifest.json`;
- workflows e templates em `.github/`.

Mantenha `runIssueGeneration` e `runProjectCreation` desativados até concluir a personalização.

## 9. Revisar o plano completo

```bash
make plan
```

O plano é sempre dry-run.

## 10. Aplicar a configuração completa

Sem `LIVE=1`, `make apply` continua em dry-run:

```bash
make apply
```

A escrita exige confirmação explícita:

```bash
make apply LIVE=1
```

Também existe o atalho combinado explícito:

```bash
make setup-live
```

## 11. Executar módulos individualmente

Primeiro execute em dry-run:

```bash
make labels
make milestones
make issues
make project-create
make project-sync
```

`make project-sync` usa `PROJECT_SETUP_PROJECT_NUMBER` quando ele estiver definido no `.env`. Antes disso, é possível informar o número apenas naquela execução:

```bash
make project-sync PROJECT_NUMBER=1
```

Após revisar a saída, habilite a escrita explicitamente:

```bash
make labels LIVE=1
make milestones LIVE=1
make issues LIVE=1
make project-create LIVE=1
make project-sync LIVE=1
```

Operações reais de Project v2 exigem `PROJECT_SETUP_PAT` no `.env`.

Sem PAT, `project-sync` em dry-run produz um preview offline da definição local e informa que a comparação remota não foi executada.

## 12. Overrides pontuais

A configuração persistente reduz os comandos normais, mas não impede operar outro alvo sem editar o `.env`:

```bash
make plan TARGET=../outro-projeto REPO=owner/outro-repo
make project-sync PROJECT_NUMBER=2
```

A precedência prática é:

1. valor informado diretamente no comando `make`;
2. valor resolvido do `.env`;
3. default interno quando aplicável.

## 13. Execução manual no Actions

No repositório-alvo:

**Actions** → **Project setup** → **Run workflow**

Comece com `dry_run=true`. A criação real de Project v2 exige o secret `PROJECT_SETUP_PAT`.

## Recuperação

1. execute `make help` e confirme alvo/repositório resolvidos;
2. execute `make doctor`;
3. siga cada instrução `Fix:`;
4. execute `make check`;
5. repita `make plan`;
6. aplique somente após revisar a saída.

Labels e milestones são sincronizados de forma idempotente. A geração de issues ainda não é idempotente e não deve ser repetida sem revisar as issues existentes.
