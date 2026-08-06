from __future__ import annotations

import json

from .github import GitHubClient


def load_backlog(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if "phases" not in data or not isinstance(data["phases"], list):
        raise ValueError("backlog manifest must contain a phases list")
    return data


def task_title(task: str | dict) -> str:
    if isinstance(task, str):
        return task
    title = task.get("title")
    if not title:
        raise ValueError("task objects must define title")
    return str(title)


def issue_node_id(client: GitHubClient, repo: str, number: int) -> str:
    owner, name = repo.split("/", 1)
    query = """
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) { issue(number:$number) { id } }
    }
    """
    data = client.graphql(query, {"owner": owner, "repo": name, "number": number})
    issue = data["repository"]["issue"]
    if not issue:
        raise RuntimeError(f"Issue #{number} was not found in {repo}")
    return issue["id"]


def add_sub_issue(client: GitHubClient, repo: str, parent_number: int, child_number: int) -> None:
    mutation = """
    mutation($parent:ID!, $child:ID!) {
      addSubIssue(input:{issueId:$parent, subIssueId:$child}) { clientMutationId }
    }
    """
    client.graphql(
        mutation,
        {
            "parent": issue_node_id(client, repo, parent_number),
            "child": issue_node_id(client, repo, child_number),
        },
    )


def generate_issues(
    client: GitHubClient | None,
    repo: str,
    manifest: str,
    dry_run: bool = False,
    link_subissues: bool = False,
) -> None:
    data = load_backlog(manifest)
    default_labels = data.get("defaultIssueLabels", [])
    for phase in data["phases"]:
        milestone = phase.get("milestone", "")
        for story in phase.get("stories", []):
            story_labels = list(dict.fromkeys([*story.get("labels", []), *default_labels]))
            story_body = "\n\n".join(
                [
                    story.get("body", "## Context\n- Describe the expected outcome."),
                    f"## Acceptance criteria\n{story.get('acceptanceCriteria', '- Define acceptance criteria.')}",
                    f"## Test strategy\n{story.get('testStrategy', '- Define the test strategy.')}",
                    f"## Definition of Done\n{story.get('dod', '- Define the completion criteria.')}",
                    f"- Milestone: {milestone}\n- Item type: user-story",
                ]
            )
            if dry_run:
                print(f"[DRY-RUN] Story: {story['title']} labels={story_labels}")
                story_number = None
            else:
                if not client:
                    raise RuntimeError("A GitHub client is required outside dry-run mode")
                created_story = client.create_issue(repo, story["title"], story_body, story_labels)
                story_number = int(created_story["number"])
                print(f"Created story #{story_number}: {story['title']}")

            for task in story.get("tasks", []):
                title = task_title(task)
                task_labels = ["type:task", "status:backlog"]
                parent_reference = f"{story.get('storyId', 'US-XX')}"
                if story_number:
                    parent_reference += f" (#{story_number})"
                task_body = "\n\n".join(
                    [
                        f"Parent story: {parent_reference}",
                        "## Technical scope\n- Define the implementation scope.",
                        "## Completion criteria\n- Define objective completion criteria.",
                        "## Test strategy\n- Define automated, smoke, or manual validation.",
                        "## Expected evidence\n- Attach relevant evidence.",
                        "## Definition of Done\n- Scope implemented and validated.",
                        "- Item type: task/sub-issue",
                    ]
                )
                if dry_run:
                    print(f"[DRY-RUN]   Task: {title} labels={task_labels}")
                    continue
                assert client is not None and story_number is not None
                created_task = client.create_issue(repo, title, task_body, task_labels)
                task_number = int(created_task["number"])
                print(f"  Created task #{task_number}: {title}")
                if link_subissues:
                    add_sub_issue(client, repo, story_number, task_number)
                    print(f"    Linked #{task_number} as sub-issue of #{story_number}")
