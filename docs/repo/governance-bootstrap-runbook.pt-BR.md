# Runbook — Bootstrap de governança

## 1) Permissões necessárias
Para criar/editar Project, labels, issues e sub-issues automaticamente, use uma conta com:
- acesso **Admin** ao repositório
- permissão para **Projects** (Project v2)
- token com escopos: `repo`, `project` e `read:org` (se necessário)

## 2) Como conceder admin no GitHub
1. Repositório -> **Settings** -> **Collaborators and teams**.
2. Adicione o usuário/conta que executará as automações.
3. Defina role **Admin**.
4. Em **Settings -> Actions -> General**, permita:
   - `Read and write permissions` para o `GITHUB_TOKEN`;
   - criação e aprovação de PRs por GitHub Actions (se desejado).
5. Para criar **Project v2**, autentique o `gh` com PAT contendo escopo `project` (além de `repo`).
6. Antes de executar qualquer comando, rode `bash scripts/github/bootstrap_local.sh` para ver o guia, confirmar se quer prosseguir e seguir o fluxo passo a passo.

## 3) Como executar agora
### Opção A — Workflow manual (recomendado)
1. Push desta branch.
2. GitHub -> **Actions** -> `Governance bootstrap (manual)` -> **Run workflow**.
3. Rodar `dry_run=true` primeiro.
4. Rodar `dry_run=false` para criar labels, milestones, issues/tasks/sub-issues e Project, conforme os inputs escolhidos.

### Opção B — Local com script único
> Segurança: evite colocar PAT diretamente no histórico do shell. Prefira carregar via gerenciador de segredos, arquivo de ambiente local não versionado, ou prompt interativo.

```bash
gh auth login
export GITHUB_REPOSITORY=v-Kaefer/Take-Your-Pills
export GH_TOKEN=SEU_PAT_COM_PERMISSAO_PROJECT

bash scripts/github/bootstrap_local.sh --repo v-Kaefer/Take-Your-Pills
```

O wizard local vive em `scripts/github/bootstrap_local.sh` e chama a CLI reutilizável `governance_bootstrap` por baixo.

### Verificação completa local (antes de PR)
```bash
./scripts/validation/repo_quality.sh
bash scripts/github/bootstrap_local.sh --repo v-Kaefer/Take-Your-Pills
```

## 4) Observações
- Para reutilizar em outro projeto, copie/adapte os manifests em `config/project`, `config/stories` e `governance.bootstrap.json`.
- O segredo esperado pelo workflow manual é `GOVERNANCE_PAT`.
- O script local começa com um guia, pede confirmação para prosseguir e só depois confirma se `GITHUB_TOKEN`, `GH_TOKEN` ou `gh auth status` já estão configurados.
- Responsáveis por fase estão `TBD` em `config/phases/phase-review-policy.json`.
- Loja e ranking online estão marcados como stretch no manifesto.
- Base de teste Godot definida como GDUnit4 em política de testes.
