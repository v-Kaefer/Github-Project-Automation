from __future__ import annotations

import json
import os
import re
import urllib.parse

from .github import API_BASE, GitHubClient, split_repo


OWNER_TYPES = ("user", "organization")
OWNER_TYPE_ALIASES = {
    "user": "user",
    "organization": "organization",
    "org": "organization",
    "company": "organization",
}


def load_project_definition(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        definition = json.load(file)
    if not definition.get("name"):
        raise ValueError("project definition must contain name")
    return definition


def normalize_owner_type(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = OWNER_TYPE_ALIASES.get(value.strip().casefold())
    if not normalized:
        raise ValueError("Project owner type must be 'user' or 'organization'")
    return normalized


def configured_owner_type(value: str | None = None) -> str | None:
    raw_value = value if value is not None else os.getenv("PROJECT_SETUP_OWNER_TYPE")
    return normalize_owner_type(raw_value)


def resolve_owner_type(client: GitHubClient, owner: str, owner_type: str | None = None) -> str:
    configured = configured_owner_type(owner_type)
    if configured:
        return configured

    encoded_owner = urllib.parse.quote(owner, safe="")
    profile = client.request_json("GET", f"{API_BASE}/users/{encoded_owner}")
    github_type = str(profile.get("type", "")).casefold()
    if github_type == "user":
        return "user"
    if github_type == "organization":
        return "organization"
    raise RuntimeError(
        f"Could not determine whether GitHub owner '{owner}' is a user or organization. "
        "Set PROJECT_SETUP_OWNER_TYPE=user or PROJECT_SETUP_OWNER_TYPE=organization."
    )


def owner_node(client: GitHubClient, owner: str, owner_type: str | None = None) -> str:
    resolved_type = resolve_owner_type(client, owner, owner_type)
    query = f"query($login:String!){{{resolved_type}(login:$login){{id}}}}"
    node = client.graphql(query, {"login": owner}).get(resolved_type)
    if node and node.get("id"):
        return node["id"]
    raise RuntimeError(f"GitHub {resolved_type} owner not found: {owner}")


def create_project(
    client: GitHubClient,
    repo: str,
    definition_file: str,
    dry_run: bool = False,
    owner_type: str | None = None,
) -> None:
    definition = load_project_definition(definition_file)
    owner = split_repo(repo)[0]
    configured_type = configured_owner_type(owner_type)
    if dry_run:
        print(f"[DRY-RUN] Would create Project v2: {definition['name']}")
        print(f"- owner: {owner}")
        print(f"- owner type: {configured_type or 'auto-detect during authenticated execution'}")
        for field in definition.get("fields", []):
            print(f"- field: {field['name']} ({field['type']})")
        return
    mutation = """
    mutation($owner:ID!, $title:String!) {
      createProjectV2(input:{ownerId:$owner,title:$title}) { projectV2 { id number title url } }
    }
    """
    project = client.graphql(
        mutation,
        {"owner": owner_node(client, owner, configured_type), "title": definition["name"]},
    )["createProjectV2"]["projectV2"]
    print(json.dumps(project, ensure_ascii=False))


def find_project(
    client: GitHubClient,
    owner: str,
    project_number: int,
    owner_type: str | None = None,
) -> dict:
    resolved_type = resolve_owner_type(client, owner, owner_type)
    query = f"""
    query($login:String!, $number:Int!) {{
      {resolved_type}(login:$login) {{ projectV2(number:$number) {{ id title url }} }}
    }}
    """
    data = client.graphql(query, {"login": owner, "number": project_number})
    node = data.get(resolved_type)
    if node and node.get("projectV2"):
        return node["projectV2"]
    raise RuntimeError(f"Project v2 #{project_number} not found for {resolved_type} '{owner}'")


def list_project_fields(client: GitHubClient, project_id: str) -> list[dict]:
    query = """
    query($project:ID!, $cursor:String) {
      node(id:$project) {
        ... on ProjectV2 {
          fields(first:100, after:$cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              __typename
              ... on ProjectV2Field { id name dataType }
              ... on ProjectV2SingleSelectField { id name dataType options { id name } }
            }
          }
        }
      }
    }
    """
    fields: list[dict] = []
    cursor = None
    while True:
        page = client.graphql(query, {"project": project_id, "cursor": cursor})["node"]["fields"]
        fields.extend(field for field in page["nodes"] if field)
        if not page["pageInfo"]["hasNextPage"]:
            return fields
        cursor = page["pageInfo"]["endCursor"]


def create_field(client: GitHubClient, project_id: str, field: dict) -> None:
    field_type = field.get("type")
    if field_type == "text":
        mutation = """
        mutation($project:ID!, $name:String!) {
          createProjectV2Field(input:{projectId:$project,name:$name,dataType:TEXT}) {
            projectV2Field { ... on ProjectV2Field { id } }
          }
        }
        """
        client.graphql(mutation, {"project": project_id, "name": field["name"]})
        return
    if field_type == "single_select":
        mutation = """
        mutation($project:ID!, $name:String!, $options:[ProjectV2SingleSelectFieldOptionInput!]!) {
          createProjectV2Field(input:{projectId:$project,name:$name,dataType:SINGLE_SELECT,singleSelectOptions:$options}) {
            projectV2Field { ... on ProjectV2SingleSelectField { id } }
          }
        }
        """
        options = [
            {"name": option, "color": "GRAY", "description": ""}
            for option in field.get("options", [])
        ]
        client.graphql(mutation, {"project": project_id, "name": field["name"], "options": options})
        return
    raise ValueError(f"Unsupported project field type: {field_type}")


def ensure_fields(client: GitHubClient, project_id: str, definition: dict, dry_run: bool = False) -> dict[str, dict]:
    existing = {field["name"]: field for field in list_project_fields(client, project_id) if field.get("name")}
    for field in definition.get("fields", []):
        if field["name"] in existing:
            continue
        if dry_run:
            print(f"[DRY-RUN] Would create field: {field['name']} ({field['type']})")
        else:
            create_field(client, project_id, field)
            print(f"created field: {field['name']}")
    if dry_run:
        return existing
    return {field["name"]: field for field in list_project_fields(client, project_id) if field.get("name")}


def list_repo_issues(client: GitHubClient, repo: str, state: str = "open") -> list[dict]:
    issues = client.paginated(f"{API_BASE}/repos/{repo}/issues?state={state}&sort=created&direction=asc")
    return [issue for issue in issues if "pull_request" not in issue]


def issue_node_id(client: GitHubClient, repo: str, number: int) -> str:
    owner, name = split_repo(repo)
    query = """
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner,name:$repo) { issue(number:$number) { id } }
    }
    """
    issue = client.graphql(query, {"owner": owner, "repo": name, "number": number})["repository"]["issue"]
    if not issue:
        raise RuntimeError(f"Issue #{number} not found in {repo}")
    return issue["id"]


def list_project_items(client: GitHubClient, project_id: str) -> dict[str, str]:
    query = """
    query($project:ID!, $cursor:String) {
      node(id:$project) {
        ... on ProjectV2 {
          items(first:100,after:$cursor) {
            pageInfo { hasNextPage endCursor }
            nodes { id content { __typename ... on Issue { id } } }
          }
        }
      }
    }
    """
    result: dict[str, str] = {}
    cursor = None
    while True:
        page = client.graphql(query, {"project": project_id, "cursor": cursor})["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content")
            if content and content.get("__typename") == "Issue":
                result[content["id"]] = item["id"]
        if not page["pageInfo"]["hasNextPage"]:
            return result
        cursor = page["pageInfo"]["endCursor"]


def add_issue_to_project(client: GitHubClient, project_id: str, issue_id: str) -> str:
    mutation = """
    mutation($project:ID!, $content:ID!) {
      addProjectV2ItemById(input:{projectId:$project,contentId:$content}) { item { id } }
    }
    """
    return client.graphql(mutation, {"project": project_id, "content": issue_id})["addProjectV2ItemById"]["item"]["id"]


def update_single_select(client: GitHubClient, project_id: str, item_id: str, field_id: str, option_id: str) -> None:
    mutation = """
    mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
      updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}) {
        projectV2Item { id }
      }
    }
    """
    client.graphql(mutation, {"project": project_id, "item": item_id, "field": field_id, "option": option_id})


def update_text(client: GitHubClient, project_id: str, item_id: str, field_id: str, value: str) -> None:
    mutation = """
    mutation($project:ID!, $item:ID!, $field:ID!, $value:String!) {
      updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{text:$value}}) {
        projectV2Item { id }
      }
    }
    """
    client.graphql(mutation, {"project": project_id, "item": item_id, "field": field_id, "value": value})


def label_value(labels: list, prefix: str) -> str | None:
    for label in labels:
        name = label["name"] if isinstance(label, dict) else str(label)
        if name.startswith(prefix):
            return name.split(":", 1)[1]
    return None


def milestone_from_issue(issue: dict) -> str | None:
    milestone = issue.get("milestone")
    if milestone and milestone.get("title"):
        return milestone["title"]
    match = re.search(r"-\s*Milestone:\s*([A-Za-z0-9_.-]+)", issue.get("body") or "")
    return match.group(1) if match else None


def option_id(field: dict, desired: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "", desired.lower())
    for option in field.get("options", []):
        if re.sub(r"[^a-z0-9]+", "", option["name"].lower()) == normalized:
            return option["id"]
    return None


def sync_issue_fields(
    client: GitHubClient,
    project_id: str,
    item_id: str,
    issue: dict,
    fields: dict[str, dict],
    definition: dict,
    dry_run: bool = False,
) -> None:
    milestone = milestone_from_issue(issue)
    values = {
        "Phase": definition.get("phaseMilestoneMap", {}).get(milestone),
        "Item Type": label_value(issue.get("labels", []), "type:"),
        "Priority": label_value(issue.get("labels", []), "priority:"),
        "Status": label_value(issue.get("labels", []), "status:"),
        "Test Type": label_value(issue.get("labels", []), "test:"),
        "Milestone": milestone,
    }
    for field_name, value in values.items():
        field = fields.get(field_name)
        if not field or not value:
            continue
        if dry_run:
            print(f"[DRY-RUN] Would set {field_name}={value} on issue #{issue['number']}")
        elif field.get("dataType") == "SINGLE_SELECT":
            if selected := option_id(field, value):
                update_single_select(client, project_id, item_id, field["id"], selected)
            else:
                print(f"warning: option '{value}' not found for field '{field_name}'")
        elif field.get("dataType") == "TEXT":
            update_text(client, project_id, item_id, field["id"], value)


def sync_project(
    client: GitHubClient,
    repo: str,
    definition_file: str,
    project_number: int,
    owner: str | None = None,
    issue_state: str = "open",
    dry_run: bool = False,
    owner_type: str | None = None,
) -> None:
    definition = load_project_definition(definition_file)
    target_owner = owner or split_repo(repo)[0]
    project = find_project(client, target_owner, project_number, owner_type=owner_type)
    print(f"Project found: {project['title']} ({project['url']})")
    fields = ensure_fields(client, project["id"], definition, dry_run=dry_run)
    current_items = list_project_items(client, project["id"])
    for issue in list_repo_issues(client, repo, issue_state):
        node_id = issue.get("node_id") or issue_node_id(client, repo, int(issue["number"]))
        item_id = current_items.get(node_id)
        if not item_id:
            if dry_run:
                print(f"[DRY-RUN] Would add issue #{issue['number']} to project")
                item_id = f"dry-run-{issue['number']}"
            else:
                item_id = add_issue_to_project(client, project["id"], node_id)
                current_items[node_id] = item_id
                print(f"Added issue #{issue['number']} to project")
        sync_issue_fields(client, project["id"], item_id, issue, fields, definition, dry_run=dry_run)
