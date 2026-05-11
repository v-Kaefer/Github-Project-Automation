# Política de Branches (PT-BR)

## Branches principais
- `main`: entrega macro estável
- `develop`: branch de integração
- `milestone/<nome-do-milestone>`: branch do milestone ativo
- `feat/<milestone>/<task>` ou `task/<milestone>/<task>`: branch de implementação

## Camadas de merge
1. task -> milestone
2. milestone -> develop
3. develop -> main

## Convenção
- Convenção padrão para feature: `feat/<escopo>`
- Branch atual de bootstrap: `feat/repo-governance-bootstrap`
