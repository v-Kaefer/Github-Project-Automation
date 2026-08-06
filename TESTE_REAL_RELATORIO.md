# Relatório do teste real

Repositório testado: `v-Kaefer/Github-Project-Automation`

## Resultado

O teste real foi concluído com sucesso:

- Project criado: [Project Delivery Board #6](https://github.com/users/v-Kaefer/projects/6)
- Issue criada: [#7 — US-00](https://github.com/v-Kaefer/Github-Project-Automation/issues/7)
- Tasks criadas: [#8 — T-00.1](https://github.com/v-Kaefer/Github-Project-Automation/issues/8) e [#9 — T-00.2](https://github.com/v-Kaefer/Github-Project-Automation/issues/9)

## O que deu errado inicialmente

### 1. A autenticação local do `gh` estava inválida

O comando `gh auth status` informou que o token da conta `v-Kaefer` estava inválido. Isso impediu a validação usando o cliente `gh`, mas não afetou a execução posterior pelo token configurado no `.env`.

### 2. O Makefile não funcionou diretamente no shell padrão do Windows

A primeira execução de `make` falhou por dois motivos de portabilidade:

- o Makefile usa `python3`, que não estava disponível com esse nome no Windows;
- as regras `require-repo` e semelhantes usam o comando Unix `test`, que não existe no `cmd.exe`.

### 3. A primeira tentativa com a CLI usou uma opção inexistente

Foi tentado usar `--no-dry-run`, mas a CLI não possui essa opção. O comportamento correto é:

- `--dry-run`: simulação;
- sem `--dry-run`: execução real.

Essa tentativa falhou antes de fazer qualquer alteração.

### 4. A sandbox bloqueou a conexão com o GitHub

Mesmo com o Makefile corrigido para usar `python` e um shell POSIX, a execução recebeu `WinError 10013`, indicando bloqueio de rede pela sandbox. Após autorizar a conexão externa, as operações foram concluídas.

## Comando que funcionou no Windows

```powershell
make SHELL='C:/Program Files/Git/bin/sh.exe' PYTHON=python project-create REPO=v-Kaefer/Github-Project-Automation LIVE=1
make SHELL='C:/Program Files/Git/bin/sh.exe' PYTHON=python issues REPO=v-Kaefer/Github-Project-Automation LIVE=1
```

## Conclusão

Não houve falha na lógica de criação do Project, da issue ou das tasks. Os problemas encontrados foram relacionados ao ambiente Windows, à autenticação do `gh` e à restrição de rede da sandbox.
