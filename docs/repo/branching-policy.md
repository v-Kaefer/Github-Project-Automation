# Branching Policy (EN)

## Main branches
- `main`: stable macro delivery
- `develop`: integration branch
- `milestone/<milestone-name>`: active milestone branch
- `feat/<milestone>/<task-name>` or `task/<milestone>/<task-name>`: implementation branch

## Merge layers
1. task -> milestone
2. milestone -> develop
3. develop -> main

## Naming
- Feature convention default: `feat/<scope>`
- Current bootstrap branch: `feat/repo-governance-bootstrap`
