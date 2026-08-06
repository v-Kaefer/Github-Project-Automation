# Runbook — GitHub Project Setup

## Objetivo

Instalar e operar as automações deste repositório em outro projeto sem sobrescrever arquivos existentes ou executar alterações remotas antes de uma revisão.

## 1. Validar a ferramenta

```bash
make check
```

O comando compila o pacote, valida a estrutura do repositório e executa os testes.

## 2. Inspecionar o repositório-alvo

Registre a linguagem, framework, comandos de teste, branches principais, labels, milestones, Project v2 e workflows existentes. Para descoberta automática inicial:

```bash
make discover TARGET=../meu-projeto REPO=owner/repositorio
```

## 3. Simular a instalação

```bash
make init-dry TARGET=../meu-projeto PROFILE=core
```

Use `PROFILE=godot` apenas quando o projeto realmente utilizar Godot.

## 4. Instalar os arquivos

```bash
make init TARGET=../meu-projeto
```

Arquivos existentes são preservados. A substituição consciente exige `FORCE=1`.

## 5. Personalizar

Edite no repositório-alvo:

- `project_setup.json`;
- `config/project/labels.json`;
- `config/project/milestones.json`;
- `config/project/project-definition.json`;
- `config/stories/backlog-manifest.json`;
- workflows e templates em `.github/`.

Mantenha `runIssueGeneration` e `runProjectCreation` desativados até concluir a personalização.

## 6. Configurar autenticação

Para execução local, configure `GITHUB_TOKEN`, `GH_TOKEN` ou `PROJECT_SETUP_PAT`. Uma sessão autenticada do GitHub CLI também pode ser usada por meio de `gh auth token`.

Para Actions, configure o secret `PROJECT_SETUP_PAT` quando Project v2 ou permissões adicionais forem necessários.

## 7. Revisar o plano

```bash
make plan TARGET=../meu-projeto REPO=owner/repositorio
```

Revise integralmente a saída antes de continuar.

## 8. Aplicar

```bash
make apply TARGET=../meu-projeto REPO=owner/repositorio
```

## 9. Validar no GitHub

Confirme labels, milestones, ausência de issues duplicadas, disponibilidade do workflow `Project setup`, validação dos PRs e criação do Project v2 somente quando solicitada.

## Recuperação

1. execute `python -m project_setup doctor` no repositório-alvo;
2. confirme o token e suas permissões;
3. execute novamente com `--dry-run`;
4. corrija o manifest responsável;
5. evite `FORCE=1` até identificar o arquivo conflitante.

O sincronismo de labels e milestones é idempotente. A geração de issues não é idempotente e não deve ser repetida sem revisar as issues existentes.
