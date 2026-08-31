from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .github import API_BASE, GitHubClient, split_repo


SUPPORTED_RULE_TYPES = {
    "pull_request", "required_status_checks", "non_fast_forward", "deletion",
    "required_linear_history", "required_deployments",
}


def load_rulesets(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rulesets = data.get("rulesets") if isinstance(data, dict) else None
    if not isinstance(rulesets, list):
        raise ValueError("rulesets manifest must contain a rulesets list")
    names: set[str] = set()
    for item in rulesets:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("each ruleset needs a non-empty name")
        if item["name"] in names:
            raise ValueError(f"duplicate ruleset name: {item['name']}")
        names.add(item["name"])
        if item.get("target", "branch") != "branch":
            raise ValueError("this GPA release supports branch rulesets only")
        for rule in item.get("rules", []):
            if rule.get("type") not in SUPPORTED_RULE_TYPES:
                raise ValueError(f"unsupported ruleset rule: {rule.get('type')}")
    return rulesets


def _actor(client: GitHubClient, owner: str, actor: dict[str, Any]) -> dict[str, Any]:
    actor_type = actor.get("type")
    mode = actor.get("mode", "pull_request")
    if actor_type == "team":
        slug = actor.get("slug")
        if not slug:
            raise ValueError("team bypass actor requires slug")
        item = client.request_json("GET", f"{API_BASE}/orgs/{owner}/teams/{slug}")
        return {"actor_id": item["id"], "actor_type": "Team", "bypass_mode": mode}
    if actor_type == "user":
        login = actor.get("login")
        if not login:
            raise ValueError("user bypass actor requires login")
        item = client.request_json("GET", f"{API_BASE}/users/{login}")
        return {"actor_id": item["id"], "actor_type": "User", "bypass_mode": mode}
    if actor_type == "organization_admin":
        return {"actor_id": None, "actor_type": "OrganizationAdmin", "bypass_mode": mode}
    if actor_type == "repository_role":
        role_id = actor.get("id")
        if role_id is None:
            raise ValueError("repository_role bypass actor requires id")
        return {"actor_id": role_id, "actor_type": "RepositoryRole", "bypass_mode": mode}
    raise ValueError(f"unsupported bypass actor type: {actor_type}")


def desired_ruleset(client: GitHubClient, repo: str, definition: dict[str, Any]) -> dict[str, Any]:
    owner, _ = split_repo(repo)
    return {
        "name": definition["name"],
        "target": "branch",
        "enforcement": definition.get("enforcement", "active"),
        "conditions": {"ref_name": definition.get("refName", {"include": ["~DEFAULT_BRANCH"]})},
        "rules": definition.get("rules", []),
        "bypass_actors": [_actor(client, owner, item) for item in definition.get("bypassActors", [])],
    }


def _comparison(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value.get(key) for key in ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")}


def plan_rulesets(client: GitHubClient, repo: str, path: str) -> tuple[str, list[tuple[str, dict[str, Any], int | None]]]:
    desired = [desired_ruleset(client, repo, item) for item in load_rulesets(path)]
    current = client.request_json("GET", f"{API_BASE}/repos/{repo}/rulesets")
    by_name = {item.get("name"): item for item in current}
    actions: list[tuple[str, dict[str, Any], int | None]] = []
    for item in desired:
        existing = by_name.get(item["name"])
        if not existing:
            actions.append(("create", item, None))
            continue
        full = client.request_json("GET", f"{API_BASE}/repos/{repo}/rulesets/{existing['id']}")
        actions.append(("unchanged" if _comparison(full) == _comparison(item) else "update", item, int(existing["id"])))
    fingerprint = {
        "repo": repo,
        "actions": [
            {"action": action, "id": identifier, "ruleset": _comparison(item)}
            for action, item, identifier in actions
        ],
    }
    plan_id = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()[:12]
    for action, item, identifier in actions:
        print(f"{action}: {item['name']}" + (f" (id={identifier})" if identifier else ""))
    print(f"plan-id={plan_id}")
    return plan_id, actions


def apply_rulesets(client: GitHubClient, repo: str, path: str, confirmation: str) -> None:
    plan_id, actions = plan_rulesets(client, repo, path)
    if confirmation != plan_id:
        raise ValueError(f"ruleset changes require --confirm {plan_id}")
    for action, item, identifier in actions:
        if action == "create":
            client.request_json("POST", f"{API_BASE}/repos/{repo}/rulesets", item)
        elif action == "update":
            client.request_json("PUT", f"{API_BASE}/repos/{repo}/rulesets/{identifier}", item)
    print("Ruleset reconciliation completed. No undeclared rulesets were deleted.")
