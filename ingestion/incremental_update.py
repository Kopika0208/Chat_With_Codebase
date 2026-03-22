from typing import Any, Dict, Optional

from .api_ingestion import (
    GitHubAPISource,
    _load_all_artifacts,
    _load_existing_contributions,
    _load_metadata,
    _materialize_outputs,
    _persist_artifact,
    _remove_cached_file,
    _save_metadata,
    _submit_worker_batch,
    ingest_repo_via_api,
)
from .github_contributions import extract_contributions_via_api, save_contributions
from .github_loader import get_changed_files


def update_repo_via_api(repo_id: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Incrementally refresh a previously API-ingested repository."""
    metadata = _load_metadata(repo_id)
    if not metadata:
        return ingest_repo_via_api(repo_id, token=token)

    repo_url = metadata.get("repo_url")
    if not repo_url:
        raise ValueError(f"Missing repo_url in metadata for {repo_id}")

    source = GitHubAPISource(
        repo_url,
        branch=metadata.get("branch"),
        token=token,
    )

    last_commit_sha = metadata.get("last_commit_sha")
    head_commit = source.get_head_commit()
    head_sha = head_commit.get("sha")
    if not head_sha:
        raise ValueError(f"Could not determine HEAD commit for {repo_url}")

    if not last_commit_sha or last_commit_sha == head_sha:
        return {
            "repo_name": repo_id,
            "status": "up_to_date",
            "updated_files": 0,
            "removed_files": 0,
            "head_sha": head_sha,
        }

    changed = get_changed_files(
        source.owner,
        source.repo,
        last_commit_sha,
        head_sha,
        token=source.token,
        session=source.session,
    )

    changed_paths = sorted(set(changed.get("added", [])) | set(changed.get("modified", [])))
    removed_paths = sorted(set(changed.get("removed", [])))
    if not changed_paths and not removed_paths:
        metadata["last_commit_sha"] = head_sha
        metadata["last_commit_message"] = head_commit.get("message") or metadata.get("last_commit_message")
        metadata["last_commit_date"] = head_commit.get("date") or metadata.get("last_commit_date")
        _save_metadata(repo_id, metadata)
        return {
            "repo_name": repo_id,
            "status": "up_to_date",
            "updated_files": 0,
            "removed_files": 0,
            "head_sha": head_sha,
        }

    tree_index = {entry["path"]: entry for entry in source.list_files() if entry.get("path")}
    changed_entries = [tree_index[path] for path in changed_paths if path in tree_index]

    for rel_path in removed_paths:
        _remove_cached_file(repo_id, rel_path)

    processed = _submit_worker_batch(
        source,
        repo_id,
        changed_entries,
        head_sha,
        head_commit.get("message") or "No commit message found",
        head_commit.get("date"),
    )

    file_shas = dict(metadata.get("file_shas", {}))
    for rel_path in removed_paths:
        file_shas.pop(rel_path, None)

    for rel_path, sha, result in processed:
        file_shas[rel_path] = sha or ""
        _persist_artifact(repo_id, rel_path, sha, result)

    all_results = _load_all_artifacts(repo_id)
    materialized = _materialize_outputs(
        repo_id,
        all_results,
        head_sha,
        head_commit.get("message") or "No commit message found",
        head_commit.get("date"),
        return_data=False,
    )

    metadata.update(
        {
            "source_type": "github_api",
            "repo_url": repo_url,
            "owner": source.owner,
            "repo": source.repo,
            "branch": source.branch,
            "last_commit_sha": head_sha,
            "last_commit_message": head_commit.get("message") or metadata.get("last_commit_message"),
            "last_commit_date": head_commit.get("date") or metadata.get("last_commit_date"),
            "file_shas": file_shas,
        }
    )
    _save_metadata(repo_id, metadata)

    contributions = extract_contributions_via_api(
        source.owner,
        source.repo,
        source.token,
        branch=source.branch,
        existing_data=_load_existing_contributions(repo_id),
    )
    save_contributions(repo_id, contributions)

    return {
        "repo_name": repo_id,
        "status": "updated",
        "updated_files": len(processed),
        "removed_files": len(removed_paths),
        "head_sha": head_sha,
        "materialized": materialized,
    }
