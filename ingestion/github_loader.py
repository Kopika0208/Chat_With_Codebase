import base64
import time
from typing import Any, Dict, List, Optional

import requests


GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 4


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API returns an unrecoverable error."""


def _build_headers(token: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_json(
    path: str,
    token: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    client = session or requests.Session()
    url = f"{GITHUB_API_BASE}{path}"
    backoff = 1.0

    for attempt in range(MAX_RETRIES):
        response = client.get(url, headers=_build_headers(token), params=params, timeout=DEFAULT_TIMEOUT)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset_at = response.headers.get("X-RateLimit-Reset")
            if remaining == "0" and reset_at:
                wait_seconds = max(1, min(int(reset_at) - int(time.time()), 60))
            else:
                wait_seconds = min(int(backoff), 15)
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait_seconds)
                backoff *= 2
                continue

        if response.status_code in (500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
            time.sleep(min(int(backoff), 15))
            backoff *= 2
            continue

        raise GitHubAPIError(
            f"GitHub API request failed ({response.status_code}) for {path}: {response.text[:300]}"
        )

    raise GitHubAPIError(f"GitHub API request exceeded retries for {path}")


def get_repo_metadata(owner: str, repo: str, token: Optional[str] = None) -> Dict[str, Any]:
    return _request_json(f"/repos/{owner}/{repo}", token=token)


def get_repo_tree(
    owner: str,
    repo: str,
    branch: str,
    token: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    payload = _request_json(
        f"/repos/{owner}/{repo}/git/trees/{branch}",
        token=token,
        params={"recursive": "1"},
        session=session,
    )
    return [entry for entry in payload.get("tree", []) if entry.get("type") == "blob"]


def get_file_content(
    owner: str,
    repo: str,
    path: str,
    branch: str,
    token: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> str:
    payload = _request_json(
        f"/repos/{owner}/{repo}/contents/{path}",
        token=token,
        params={"ref": branch},
        session=session,
    )
    if payload.get("type") != "file":
        raise GitHubAPIError(f"Expected file content for {path}, got {payload.get('type')}")

    encoded = payload.get("content", "")
    if payload.get("encoding") != "base64":
        raise GitHubAPIError(f"Unsupported encoding for {path}: {payload.get('encoding')}")

    raw_bytes = base64.b64decode(encoded)
    if b"\x00" in raw_bytes:
        raise GitHubAPIError(f"Binary file detected for {path}")
    return raw_bytes.decode("utf-8", errors="ignore")


def get_commit_details(
    owner: str,
    repo: str,
    ref: str,
    token: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, Optional[str]]:
    payload = _request_json(f"/repos/{owner}/{repo}/commits/{ref}", token=token, session=session)
    commit = payload.get("commit", {})
    author = commit.get("author", {}) if isinstance(commit, dict) else {}
    return {
        "sha": payload.get("sha"),
        "message": (commit.get("message") or "").strip().split("\n")[0] if isinstance(commit, dict) else "",
        "date": author.get("date"),
    }


def get_changed_files(
    owner: str,
    repo: str,
    base_sha: str,
    head_ref: str,
    token: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    payload = _request_json(
        f"/repos/{owner}/{repo}/compare/{base_sha}...{head_ref}",
        token=token,
        session=session,
    )

    added: List[str] = []
    modified: List[str] = []
    removed: List[str] = []

    for entry in payload.get("files", []):
        status = entry.get("status")
        filename = entry.get("filename")
        previous_filename = entry.get("previous_filename")
        if not filename:
            continue

        if status == "added":
            added.append(filename)
        elif status == "removed":
            removed.append(filename)
        elif status == "renamed":
            if previous_filename:
                removed.append(previous_filename)
            modified.append(filename)
        else:
            modified.append(filename)

    return {
        "added": sorted(set(added)),
        "modified": sorted(set(modified)),
        "removed": sorted(set(removed)),
        "head_sha": payload.get("merge_base_commit", {}).get("sha") or payload.get("commits", [{}])[-1].get("sha"),
        "files": payload.get("files", []),
    }
