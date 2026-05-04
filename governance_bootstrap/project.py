from __future__ import annotations

import json
import re

from .github import API_BASE, GitHubClient, split_repo


def load_project_definition(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        definition = json.load(f)
    if "name" not in definition:
        raise ValueError("project definition must contain name")
    return definition


def owner_node(client: GitHubClient, owner: str) -> str:
    query_user = "query($login:String!){user(login:$login){id}}"
    data = client.graphql(query_user, {"login": owner})
    user = data.get("user")
    if user and user.get("id"):
        return user["id"]
    query_org = "query($login:String!){organization(login:$login){id}}"
    data = client.graphql(query_org, {"login": owner})
    org = data.get("organization")
    if org and org.get("id"):
        return org["id"]
    raise RuntimeError(f"Owner not found: {owner}")


def create_project(client: GitHubClient, repo: str, definition_file: str, dry_run: bool = False) -> None:
    definition = load_project_definition(definition_file)
    owner = split_repo(repo)[0]
    if dry_run:
        print(f"[DRY-RUN] Would create project: {definition['name']}")
        print("[DRY-RUN] Fields to configure:")
        for field in definition.get("fields", []):
            print(f"- {field['name']} ({field['type']})")
        return

    oid = owner_node(client, owner)
    mutation = """
    mutation($owner:ID!, $title:String!) {
      createProjectV2(input:{ownerId:$owner,title:$title}) {
        projectV2 { id url }
      }
    }
    """
    data = client.graphql(mutation, {"owner": oid, "title": definition["name"]})
    project = data["createProjectV2"]["projectV2"]
    print(json.dumps(project, ensure_ascii=False))
    print(f"Project created. Configure custom fields and views using {definition_file}.")


def find_project(client: GitHubClient, owner: str, project_number: int) -> tuple[dict, str]:
    query_user = """
    query($login:String!, $number:Int!) {
      user(login:$login) { projectV2(number:$number) { id title url } }
    }
    """
    data = client.graphql(query_user, {"login": owner, "number": project_number})
    user = data.get("user")
    if user and user.get("projectV2"):
        return user["projectV2"], "user"

    query_org = """
    query($login:String!, $number:Int!) {
      organization(login:$login) { projectV2(number:$number) { id title url } }
    }
    """
    data = client.graphql(query_org, {"login": owner, "number": project_number})
    org = data.get("organization")
    if org and org.get("projectV2"):
        return org["projectV2"], "org"
    raise RuntimeError(f"Project v2 #{project_number} not found for owner '{owner}'")


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
              ... on ProjectV2IterationField { id name dataType }
            }
          }
        }
      }
    }
    """
    fields = []
    cursor = None
    while True:
        data = client.graphql(query, {"project": project_id, "cursor": cursor})
        page = data["node"]["fields"]
        fields.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return fields
        cursor = page["pageInfo"]["endCursor"]


def create_text_field(client: GitHubClient, project_id: str, name: str) -> dict:
    mutation = """
    mutation($project:ID!, $name:String!) {
      createProjectV2Field(input:{projectId:$project, name:$name, dataType:TEXT}) {
        projectV2Field { ... on ProjectV2Field { id name dataType } }
      }
    }
    """
    data = client.graphql(mutation, {"project": project_id, "name": name})
    return data["createProjectV2Field"]["projectV2Field"]


def create_single_select_field(client: GitHubClient, project_id: str, name: str, options: list[str]) -> dict:
    mutation = """
    mutation($project:ID!, $name:String!, $options:[ProjectV2SingleSelectFieldOptionInput!]!) {
      createProjectV2Field(input:{projectId:$project, name:$name, dataType:SINGLE_SELECT, singleSelectOptions:$options}) {
        projectV2Field { ... on ProjectV2SingleSelectField { id name dataType options { id name } } }
      }
    }
    """
    option_payload = [{"name": opt, "color": "GRAY", "description": ""} for opt in options]
    data = client.graphql(mutation, {"project": project_id, "name": name, "options": option_payload})
    return data["createProjectV2Field"]["projectV2Field"]


def ensure_fields(client: GitHubClient, project_id: str, definition: dict, dry_run: bool = False) -> dict:
    existing = list_project_fields(client, project_id)
    by_name = {f["name"]: f for f in existing if f and f.get("name")}
    for field in definition.get("fields", []):
        name = field["name"]
        if name in by_name:
            continue
        if dry_run:
            print(f"[DRY-RUN] Would create field: {name} ({field['type']})")
            continue
        if field["type"] == "text":
            created = create_text_field(client, project_id, name)
        elif field["type"] == "single_select":
            created = create_single_select_field(client, project_id, name, field.get("options", []))
        else:
            print(f"Skipping unsupported field type: {field['type']} ({name})")
            continue
        print(f"created field: {name}")
        by_name[name] = created
    if dry_run:
        return by_name
    return {f["name"]: f for f in list_project_fields(client, project_id) if f and f.get("name")}


def list_repo_issues(client: GitHubClient, repo: str, state: str = "open") -> list[dict]:
    owner, name = split_repo(repo)
    issues = client.paginated(f"{API_BASE}/repos/{owner}/{name}/issues?state={state}&sort=created&direction=asc")
    return [issue for issue in issues if "pull_request" not in issue]


def list_project_items(client: GitHubClient, project_id: str) -> dict:
    query = """
    query($project:ID!, $cursor:String) {
      node(id:$project) {
        ... on ProjectV2 {
          items(first:100, after:$cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              content { __typename ... on Issue { id number } }
            }
          }
        }
      }
    }
    """
    content_to_item = {}
    cursor = None
    while True:
        data = client.graphql(query, {"project": project_id, "cursor": cursor})
        page = data["node"]["items"]
        for item in page["nodes"]:
            content = item.get("content")
            if content and content.get("__typename") == "Issue":
                content_to_item[content["id"]] = item["id"]
        if not page["pageInfo"]["hasNextPage"]:
            return content_to_item
        cursor = page["pageInfo"]["endCursor"]


def issue_node_id(client: GitHubClient, repo: str, number: int) -> str:
    owner, name = split_repo(repo)
    query = """
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) { issue(number:$number) { id } }
    }
    """
    data = client.graphql(query, {"owner": owner, "repo": name, "number": number})
    issue = data["repository"]["issue"]
    if not issue:
        raise RuntimeError(f"Issue #{number} not found in {repo}")
    return issue["id"]


def add_issue_to_project(client: GitHubClient, project_id: str, issue_id: str) -> str:
    mutation = """
    mutation($project:ID!, $content:ID!) {
      addProjectV2ItemById(input:{projectId:$project, contentId:$content}) { item { id } }
    }
    """
    data = client.graphql(mutation, {"project": project_id, "content": issue_id})
    return data["addProjectV2ItemById"]["item"]["id"]


def add_sub_issue(client: GitHubClient, parent_id: str, child_id: str) -> None:
    mutation = """
    mutation($parent:ID!, $child:ID!) {
      addSubIssue(input:{issueId:$parent, subIssueId:$child}) { clientMutationId }
    }
    """
    client.graphql(mutation, {"parent": parent_id, "child": child_id})


def update_item_position(client: GitHubClient, project_id: str, item_id: str, after_id: str | None) -> None:
    mutation = """
    mutation($project:ID!, $item:ID!, $after:ID) {
      updateProjectV2ItemPosition(input:{projectId:$project, itemId:$item, afterId:$after}) { clientMutationId }
    }
    """
    client.graphql(mutation, {"project": project_id, "item": item_id, "after": after_id})


def update_single_select(client: GitHubClient, project_id: str, item_id: str, field_id: str, option_id: str) -> None:
    mutation = """
    mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
      updateProjectV2ItemFieldValue(input:{projectId:$project, itemId:$item, fieldId:$field, value:{singleSelectOptionId:$option}}) {
        projectV2Item { id }
      }
    }
    """
    client.graphql(mutation, {"project": project_id, "item": item_id, "field": field_id, "option": option_id})


def update_text(client: GitHubClient, project_id: str, item_id: str, field_id: str, text_value: str) -> None:
    mutation = """
    mutation($project:ID!, $item:ID!, $field:ID!, $text:String!) {
      updateProjectV2ItemFieldValue(input:{projectId:$project, itemId:$item, fieldId:$field, value:{text:$text}}) {
        projectV2Item { id }
      }
    }
    """
    client.graphql(mutation, {"project": project_id, "item": item_id, "field": field_id, "text": text_value})


def milestone_from_body(body: str) -> str | None:
    match = re.search(r"-\s*Milestone:\s*([A-Za-z0-9_.-]+)", body or "")
    return match.group(1) if match else None


def milestone_from_issue(issue: dict) -> str | None:
    milestone = issue.get("milestone")
    if milestone and milestone.get("title"):
        return milestone["title"]
    return milestone_from_body(issue.get("body", "") or "")


def parent_issue_number_from_body(body: str) -> int | None:
    match = re.search(r"Parent story:.*\(#(\d+)\)", body or "")
    return int(match.group(1)) if match else None


def label_value(labels: list, prefix: str) -> str | None:
    for label in labels:
        name = label["name"] if isinstance(label, dict) else str(label)
        if name.startswith(prefix):
            return name.split(":", 1)[1]
    return None


def option_id(field: dict, option_name: str) -> str | None:
    for opt in field.get("options", []):
        if opt["name"] == option_name:
            return opt["id"]
    return None


def sync_issue_fields(client: GitHubClient, project_id: str, item_id: str, issue: dict, fields: dict, definition: dict, dry_run: bool = False) -> None:
    labels = issue.get("labels", [])
    milestone = milestone_from_issue(issue)
    phase_map = definition.get("phaseMilestoneMap", {})
    mappings = {
        "Phase": phase_map.get(milestone),
        "Item Type": label_value(labels, "type:"),
        "Priority": label_value(labels, "priority:"),
        "Status": label_value(labels, "status:"),
        "Test Type": label_value(labels, "test:"),
        "Milestone": milestone,
    }

    for field_name, field_value in mappings.items():
        if not field_value:
            continue
        field = fields.get(field_name)
        if not field:
            continue
        if field.get("dataType") == "SINGLE_SELECT":
            oid = option_id(field, field_value)
            if not oid:
                print(f"warning: option '{field_value}' not found for field '{field_name}'")
                continue
            if dry_run:
                print(f"[DRY-RUN] Would set {field_name}={field_value} on issue #{issue['number']}")
            else:
                update_single_select(client, project_id, item_id, field["id"], oid)
        elif field.get("dataType") == "TEXT":
            if dry_run:
                print(f"[DRY-RUN] Would set {field_name}={field_value} on issue #{issue['number']}")
            else:
                update_text(client, project_id, item_id, field["id"], field_value)


def reorder_project_items(client: GitHubClient, project_id: str, issues: list[dict], current_items: dict, dry_run: bool = False) -> None:
    previous_item_id = None
    for issue in issues:
        item_id = current_items.get(issue["node_id"])
        if not item_id:
            continue
        if dry_run:
            print(f"[DRY-RUN] Would position issue #{issue['number']} after {previous_item_id or 'top'}")
        else:
            update_item_position(client, project_id, item_id, previous_item_id)
        previous_item_id = item_id


def link_subissues(client: GitHubClient, repo: str, issues: list[dict], dry_run: bool = False) -> None:
    node_ids_by_number = {issue["number"]: issue.get("node_id") for issue in issues}
    linked = 0
    skipped = 0

    for issue in issues:
        parent_number = parent_issue_number_from_body(issue.get("body", "") or "")
        if parent_number is None:
            continue

        parent_id = node_ids_by_number.get(parent_number)
        if not parent_id:
            parent_id = issue_node_id(client, repo, parent_number)
            node_ids_by_number[parent_number] = parent_id

        if dry_run:
            print(f"[DRY-RUN] Would link issue #{issue['number']} as sub-issue of #{parent_number}")
            continue

        try:
            add_sub_issue(client, parent_id, issue["node_id"])
            print(f"Linked issue #{issue['number']} as sub-issue of #{parent_number}")
            linked += 1
        except RuntimeError as exc:
            error_text = str(exc).lower()
            if (
                "already" in error_text
                or "exists" in error_text
                or "duplicate sub-issues" in error_text
                or "may only have one parent" in error_text
            ):
                print(f"Sub-issue link already exists: #{issue['number']} -> #{parent_number}")
                skipped += 1
                continue
            raise

    print(f"Sub-issue linking finished: linked={linked}, already_present={skipped}")


def sync_project(client: GitHubClient, repo: str, definition_file: str, project_number: int, owner: str | None = None, issue_state: str = "open", link_subissue_items: bool = False, only_link_subissues: bool = False, dry_run: bool = False) -> None:
    definition = load_project_definition(definition_file)
    project_owner = owner or split_repo(repo)[0]
    issues = list_repo_issues(client, repo, state=issue_state)
    for issue in issues:
        issue["node_id"] = issue_node_id(client, repo, issue["number"])

    if only_link_subissues:
        link_subissues(client, repo, issues, dry_run=dry_run)
        return

    project, owner_type = find_project(client, project_owner, project_number)
    print(f"Project found: {project['title']} ({project['url']}) owner_type={owner_type}")
    fields = ensure_fields(client, project["id"], definition, dry_run=dry_run)
    current_items = list_project_items(client, project["id"])

    for issue in issues:
        issue_id = issue["node_id"]
        item_id = current_items.get(issue_id)
        if not item_id:
            if dry_run:
                print(f"[DRY-RUN] Would add issue #{issue['number']} to project")
                item_id = f"dry-run-item-{issue['number']}"
            else:
                item_id = add_issue_to_project(client, project["id"], issue_id)
                current_items[issue_id] = item_id
                print(f"Added issue #{issue['number']} to project")
        else:
            print(f"Issue #{issue['number']} already in project")
        sync_issue_fields(client, project["id"], item_id, issue, fields, definition, dry_run=dry_run)

    reorder_project_items(client, project["id"], issues, current_items, dry_run=dry_run)
    if link_subissue_items:
        link_subissues(client, repo, issues, dry_run=dry_run)
    if definition.get("views"):
        print("Note: project views are listed in project-definition.json but are not automated by this script.")
        for view in definition["views"]:
            print(f"- create manually if needed: {view}")
