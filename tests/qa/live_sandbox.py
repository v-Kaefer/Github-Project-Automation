from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse

from project_setup.github import API_BASE, GitHubClient, split_repo
from project_setup.labels import sync_labels
from project_setup.milestones import sync_milestones
from project_setup.project import create_project, list_project_fields, sync_project


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def project_by_title(client: GitHubClient, owner: str, title: str) -> dict | None:
    query = """
    query($login:String!) {
      user(login:$login) { projectsV2(first:100) { nodes { id number title url } } }
      organization(login:$login) { projectsV2(first:100) { nodes { id number title url } } }
    }
    """
    data = client.graphql(query, {"login": owner})
    for owner_type in ("user", "organization"):
        node = data.get(owner_type)
        if not node:
            continue
        for project in node["projectsV2"]["nodes"]:
            if project and project.get("title") == title:
                return project
    return None


def find_label(client: GitHubClient, repo: str, name: str) -> list[dict]:
    return [label for label in client.paginated(f"{API_BASE}/repos/{repo}/labels") if label.get("name") == name]


def find_milestone(client: GitHubClient, repo: str, title: str) -> list[dict]:
    return [
        milestone
        for milestone in client.paginated(f"{API_BASE}/repos/{repo}/milestones?state=all")
        if milestone.get("title") == title
    ]


def delete_label(client: GitHubClient, repo: str, name: str) -> None:
    encoded = urllib.parse.quote(name, safe="")
    client.request_json("DELETE", f"{API_BASE}/repos/{repo}/labels/{encoded}")


def delete_milestone(client: GitHubClient, repo: str, number: int) -> None:
    client.request_json("DELETE", f"{API_BASE}/repos/{repo}/milestones/{number}")


def delete_project(client: GitHubClient, project_id: str) -> None:
    mutation = """
    mutation($project:ID!) {
      deleteProjectV2(input:{projectId:$project}) { projectV2 { id } }
    }
    """
    client.graphql(mutation, {"project": project_id})


def require_sandbox(repo: str) -> None:
    current_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise SystemExit("QA_REPOSITORY is missing. Configure it as an Environment variable in `qa`.")
    if "/" not in repo:
        raise SystemExit("QA_REPOSITORY must use owner/repository format.")
    if current_repo and repo.casefold() == current_repo.casefold():
        raise SystemExit(
            "Refusing live Q.A test against the source repository. "
            "Configure QA_REPOSITORY to a dedicated disposable sandbox repository."
        )
    if not os.getenv("PROJECT_SETUP_PAT", "").strip():
        raise SystemExit(
            "QA_PROJECT_SETUP_PAT is missing. Configure it in the `qa` GitHub Environment; "
            "the workflow maps it to PROJECT_SETUP_PAT only for the live sandbox job."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live, self-cleaning Q.A tests against a dedicated GitHub sandbox")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    require_sandbox(args.repo)
    token = os.environ["PROJECT_SETUP_PAT"].strip()
    client = GitHubClient(token)
    owner, _ = split_repo(args.repo)
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.run_id).strip("-")[:40] or "manual"
    label_name = f"qa:run-{suffix}"
    milestone_title = f"QA-{suffix}"
    project_title = f"QA validation {suffix}"
    created_project_id: str | None = None
    created_milestone_number: int | None = None

    print(f"sandbox_repository={args.repo}")
    print(f"qa_run_id={suffix}")

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            labels_file = root / "labels.json"
            milestones_file = root / "milestones.json"
            project_file = root / "project.json"

            write_json(
                labels_file,
                [{"name": label_name, "color": "6f42c1", "description": "Q.A first pass"}],
            )
            sync_labels(client, args.repo, str(labels_file), dry_run=False)
            labels = find_label(client, args.repo, label_name)
            if len(labels) != 1 or labels[0].get("description") != "Q.A first pass":
                raise RuntimeError("Label creation verification failed")

            write_json(
                labels_file,
                [{"name": label_name, "color": "6f42c1", "description": "Q.A verified update"}],
            )
            sync_labels(client, args.repo, str(labels_file), dry_run=False)
            sync_labels(client, args.repo, str(labels_file), dry_run=False)
            labels = find_label(client, args.repo, label_name)
            if len(labels) != 1 or labels[0].get("description") != "Q.A verified update":
                raise RuntimeError("Label update/idempotency verification failed")
            print("label_idempotency=passed")

            write_json(
                milestones_file,
                [{"title": milestone_title, "description": "Q.A first pass"}],
            )
            sync_milestones(client, args.repo, str(milestones_file), dry_run=False)
            milestones = find_milestone(client, args.repo, milestone_title)
            if len(milestones) != 1:
                raise RuntimeError("Milestone creation verification failed")
            created_milestone_number = int(milestones[0]["number"])

            write_json(
                milestones_file,
                [{"title": milestone_title, "description": "Q.A verified update"}],
            )
            sync_milestones(client, args.repo, str(milestones_file), dry_run=False)
            sync_milestones(client, args.repo, str(milestones_file), dry_run=False)
            milestones = find_milestone(client, args.repo, milestone_title)
            if len(milestones) != 1 or milestones[0].get("description") != "Q.A verified update":
                raise RuntimeError("Milestone update/idempotency verification failed")
            print("milestone_idempotency=passed")

            write_json(
                project_file,
                {
                    "name": project_title,
                    "fields": [
                        {"name": "QA Text", "type": "text"},
                        {"name": "QA Status", "type": "single_select", "options": ["Ready", "Done"]},
                    ],
                },
            )
            create_project(client, args.repo, str(project_file), dry_run=False)
            project = project_by_title(client, owner, project_title)
            if not project:
                raise RuntimeError("Project v2 creation verification failed")
            created_project_id = project["id"]

            sync_project(
                client,
                args.repo,
                str(project_file),
                int(project["number"]),
                owner=owner,
                issue_state="open",
                dry_run=False,
            )
            sync_project(
                client,
                args.repo,
                str(project_file),
                int(project["number"]),
                owner=owner,
                issue_state="open",
                dry_run=False,
            )
            fields = list_project_fields(client, created_project_id)
            qa_text = [field for field in fields if field.get("name") == "QA Text"]
            qa_status = [field for field in fields if field.get("name") == "QA Status"]
            if len(qa_text) != 1 or len(qa_status) != 1:
                raise RuntimeError("Project field idempotency verification failed")
            print("project_v2_idempotency=passed")

        print("qa_live_validation=passed")
        return 0
    finally:
        cleanup_errors: list[str] = []
        if created_project_id:
            try:
                delete_project(client, created_project_id)
                print("cleanup_project=passed")
            except Exception as exc:  # cleanup must continue for other resources
                cleanup_errors.append(f"project: {exc}")
        if created_milestone_number is not None:
            try:
                delete_milestone(client, args.repo, created_milestone_number)
                print("cleanup_milestone=passed")
            except Exception as exc:
                cleanup_errors.append(f"milestone: {exc}")
        if find_label(client, args.repo, label_name):
            try:
                delete_label(client, args.repo, label_name)
                print("cleanup_label=passed")
            except Exception as exc:
                cleanup_errors.append(f"label: {exc}")
        if cleanup_errors:
            raise RuntimeError("Q.A cleanup failed: " + "; ".join(cleanup_errors))


if __name__ == "__main__":
    raise SystemExit(main())
