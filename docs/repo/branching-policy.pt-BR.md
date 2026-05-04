# Política de Branches (PT-BR)

## Branches principais
- `main`: entrega macro estável
- `develop`: branch de integração
- `phase/<nome-da-fase>`: branch da fase ativa
- `feat/<fase>/<task>` ou `task/<fase>/<task>`: branch de implementação

## Camadas de merge
1. task -> phase
2. phase -> develop
3. develop -> main

## Convenção
- Convenção padrão para feature: `feat/<escopo>`
- Branch atual de bootstrap: `feat/repo-governance-bootstrap`
