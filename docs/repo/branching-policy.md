# Branching Policy (EN)

## Main branches
- `main`: stable macro delivery
- `develop`: integration branch
- `phase/<phase-name>`: active phase branch
- `feat/<phase>/<task-name>` or `task/<phase>/<task-name>`: implementation branch

## Merge layers
1. task -> phase
2. phase -> develop
3. develop -> main

## Naming
- Feature convention default: `feat/<scope>`
- Current bootstrap branch: `feat/repo-governance-bootstrap`
