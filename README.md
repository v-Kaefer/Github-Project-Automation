# Github-Project-Automation
Repo made to store template for projects automations



Para usar em outro repo, pense em duas partes:

  1. Ferramenta genérica: governance_bootstrap
  2. Configuração do projeto novo: manifests em config/project, config/stories e governance.bootstrap.json

  Hoje a ferramenta ainda está neste repo. O caminho ideal é publicar/colocar esse pacote em um repo próprio, por exemplo github-governance-bootstrap, e depois
  instalar no projeto consumidor.

  No outro repo
  Copie e adapte estes arquivos/pastas:

  governance.bootstrap.json
  config/project/labels.json
  config/project/milestones.json
  config/project/project-definition.json
  config/stories/backlog-manifest.json
  .github/workflows/governance-bootstrap.yml

  Depois edite:

  - labels.json: tipos, prioridades, status e labels do novo projeto.
  - milestones.json: milestones e datas do novo projeto.
  - project-definition.json: nome do board, campos, opções e phaseMilestoneMap.
  - backlog-manifest.json: fases, histórias e tasks do novo projeto.
  - workflow: use o segredo GOVERNANCE_PAT.
  - wizard local: `scripts/github/bootstrap_local.sh` mostra um guia, pede confirmação para prosseguir e então conduz o bootstrap passo a passo.

  Autenticação
  Crie no repo novo um secret:

  GOVERNANCE_PAT

  O PAT precisa conseguir mexer em:

  repo/issues
  projects
  read:org, se o repo estiver em org

  Rodar localmente
  Depois que a ferramenta estiver instalada no ambiente:

  export GH_TOKEN=SEU_PAT
  bash scripts/github/bootstrap_local.sh --repo owner/novo-repo

  Rodar pelo GitHub Actions
  No repo novo, vá em:

  Actions -> Governance bootstrap (manual) -> Run workflow

  Primeiro rode com dry_run=true. Depois rode com dry_run=false.

  Observação importante
  Se você ainda não publicou a ferramenta em um repo próprio, o workflow template precisa apontar para onde ela vai ser instalada. O arquivo de referência está
  aqui:

  docs/repo/governance-bootstrap.workflow-template.yml

  Nele, troque:

  git+https://github.com/OWNER/github-governance-bootstrap.git@v0.1.0

  pelo repo real onde você publicar a ferramenta.


Usado na branch develop de "Take Your Pills":
codex resume 019df101-f17e-7bc0-adad-6191b08617b3
