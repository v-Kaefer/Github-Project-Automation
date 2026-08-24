from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .github import GitHubClient, split_repo
from .project import resolve_owner_type


def _project_definition_title(config_path: str | os.PathLike[str]) -> str | None:
    config_file = Path(config_path)
    data = json.loads(config_file.read_text(encoding="utf-8"))
    definition_value = data.get("projectDefinitionFile")
    if not definition_value:
        return None
    definition_path = Path(str(definition_value))
    if not definition_path.is_absolute():
        definition_path = config_file.parent / definition_path
    if not definition_path.is_file():
        return None
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    title = str(definition.get("name") or "").strip()
    return title or None


def list_owner_projects(
    client: GitHubClient,
    owner: str,
    *,
    owner_type: str | None = None,
) -> list[dict[str, Any]]:
    resolved_type = resolve_owner_type(client, owner, owner_type)
    query = f"""
    query($login:String!, $cursor:String) {{
      {resolved_type}(login:$login) {{
        projectsV2(first:100, after:$cursor) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{ id number title url }}
        }}
      }}
    }}
    """
    projects: list[dict[str, Any]] = []
    cursor = None
    while True:
        data = client.graphql(query, {"login": owner, "cursor": cursor})
        node = data.get(resolved_type) or {}
        page = node.get("projectsV2") or {"nodes": [], "pageInfo": {"hasNextPage": False}}
        projects.extend(project for project in page.get("nodes", []) if project)
        page_info = page.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return projects
        cursor = page_info.get("endCursor")


def resolve_project_number(
    client: GitHubClient | None,
    repo: str,
    explicit_number: int | None,
    *,
    config_path: str | os.PathLike[str] = "project_setup.json",
    owner: str | None = None,
    owner_type: str | None = None,
) -> tuple[int | None, str]:
    if explicit_number is not None:
        return explicit_number, "configured explicitly"
    if client is None:
        return None, "Project PAT is not configured"

    title = _project_definition_title(config_path)
    if not title:
        return None, "project definition has no discoverable name"

    project_owner = owner or split_repo(repo)[0]
    matches = [
        project
        for project in list_owner_projects(client, project_owner, owner_type=owner_type)
        if str(project.get("title") or "") == title
    ]
    if len(matches) == 1:
        return int(matches[0]["number"]), f"auto-discovered by title `{title}`"
    if not matches:
        return None, f"no Project v2 named `{title}` was found"
    numbers = ", ".join(f"#{project.get('number')}" for project in matches)
    raise RuntimeError(
        f"Multiple Project v2 boards named `{title}` were found ({numbers}). "
        "Set PROJECT_SETUP_PROJECT_NUMBER explicitly."
    )
