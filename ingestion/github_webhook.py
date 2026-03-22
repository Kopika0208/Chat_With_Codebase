from typing import Any, Dict, Optional

from .incremental_update import update_repo_via_api


def handle_github_push_event(payload: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
    """Translate a GitHub push payload into an incremental update call."""
    repository = payload.get("repository", {})
    repo_url = repository.get("html_url")
    if not repo_url:
        raise ValueError("GitHub push payload is missing repository.html_url")

    repo_name = repository.get("name")
    branch_ref = payload.get("ref", "")
    branch = branch_ref.split("/")[-1] if branch_ref else None

    result = update_repo_via_api(repo_name or repo_url, token=token)
    return {
        "repository": repo_name,
        "branch": branch,
        "result": result,
    }
