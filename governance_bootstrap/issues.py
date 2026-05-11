from __future__ import annotations

import json
import os
import subprocess


def run_gh(cmd: list[str]) -> str:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"GitHub command failed. stderr:\n{result.stderr}")
    return result.stdout.strip()


def create_issue(repo: str, title: str, body: str, labels: list[str]) -> int:
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    for label in labels:
        cmd += ["--label", label]
    url = run_gh(cmd)
    parts = url.rstrip("/").split("/")
    if len(parts) < 2 or not parts[-1].isdigit():
        raise RuntimeError(f"Unexpected gh issue create output: {url}")
    return int(parts[-1])


def issue_node_id(repo: str, number: int) -> str:
    owner, name = repo.split("/", 1)
    return run_gh([
        "gh", "api", "graphql",
        "-f", "query=query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){issue(number:$number){id}}}",
        "-f", f"owner={owner}",
        "-f", f"repo={name}",
        "-F", f"number={number}",
        "--jq", ".data.repository.issue.id",
    ])


def add_sub_issue(repo: str, parent_number: int, child_number: int) -> None:
    parent_id = issue_node_id(repo, parent_number)
    child_id = issue_node_id(repo, child_number)
    run_gh([
        "gh", "api", "graphql",
        "-f", "query=mutation($parent:ID!,$child:ID!){addSubIssue(input:{issueId:$parent,subIssueId:$child}){clientMutationId}}",
        "-f", f"parent={parent_id}",
        "-f", f"child={child_id}",
    ])


def load_backlog(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "milestones" not in data:
        raise ValueError("backlog manifest must contain milestones")
    return data


def generate_issues(repo: str, manifest: str, dry_run: bool = False, link_subissues: bool = False) -> None:
    if not repo:
        repo = os.getenv("GITHUB_REPOSITORY", "")
    if not repo:
        raise SystemExit("Missing --repo and GITHUB_REPOSITORY")

    data = load_backlog(manifest)
    for milestone_entry in data["milestones"]:
        for story in milestone_entry["stories"]:
            story_labels = list(dict.fromkeys(story["labels"] + data.get("defaultIssueLabels", [])))
            story_body = (
                f"{story['body']}\n\n"
                f"## Acceptance criteria\n{story.get('acceptanceCriteria', '- TBD')}\n\n"
                f"## Test strategy\n{story.get('testStrategy', '- TBD')}\n\n"
                f"## Definition of Done\n{story.get('dod', '- TBD')}\n\n"
                f"- Milestone: {milestone_entry['milestone']}\n"
                f"- Item type: user-story\n"
            )
            if dry_run:
                print(f"[DRY-RUN] Story: {story['title']} labels={story_labels}")
                story_num = 0
            else:
                story_num = create_issue(repo, story["title"], story_body, story_labels)
                print(f"Created story #{story_num}: {story['title']}")

            for task_title in story.get("tasks", []):
                task_labels = ["type:task", "status:backlog"]
                task_body = (
                    f"Parent story: {story['storyId']}"
                    + (f" (#{story_num})" if story_num else "")
                    + "\n\n"
                    + "## Technical scope\n- TBD\n\n"
                    + "## Completion criteria\n- TBD\n\n"
                    + "## Test strategy\n- TBD\n\n"
                    + "## Expected evidence\n- TBD\n\n"
                    + "## Definition of Done\n- TBD\n\n"
                    + "- Item type: task/sub-issue\n"
                )
                if dry_run:
                    print(f"[DRY-RUN]   Task: {task_title} labels={task_labels}")
                    continue
                task_num = create_issue(repo, task_title, task_body, task_labels)
                print(f"  Created task #{task_num}: {task_title}")
                if link_subissues:
                    add_sub_issue(repo, story_num, task_num)
                    print(f"    Linked #{task_num} as sub-issue of #{story_num}")
