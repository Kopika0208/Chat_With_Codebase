"""Repository listing, ingestion, and deletion endpoints."""

import os
import shutil
import sys
import traceback
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.deps import PROJECT_ROOT, list_repos, get_repo_summary, clear_repo_cache

router = APIRouter(prefix="/api/repos", tags=["repos"])

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
EVALUATION_DIR = os.path.join(PROJECT_ROOT, "evaluation")

# Track ingestion status
_ingestion_status = {}


class IngestRequest(BaseModel):
    repo_url: str
    repo_name: Optional[str] = None


@router.get("")
def get_repos():
    """List all ingested repositories with summary stats."""
    repos = []
    for name in list_repos():
        try:
            summary = get_repo_summary(name)
            repos.append(summary)
        except Exception as e:
            repos.append({"name": name, "status": "Error", "error": str(e)})
    return {"repos": repos, "total": len(repos)}


@router.get("/{repo_name}")
def get_repo(repo_name: str):
    """Get detailed info for a single repo."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")
    return get_repo_summary(repo_name)


@router.delete("/{repo_name}")
def delete_repo(repo_name: str):
    """Delete an ingested repository's data and evaluation artifacts."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    deleted_paths = []
    missing_paths = []

    for base_dir in (DATA_DIR, EVALUATION_DIR):
        target_path = os.path.join(base_dir, repo_name)
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
            deleted_paths.append(target_path)
        else:
            missing_paths.append(target_path)

    clear_repo_cache(repo_name)

    return {
        "message": f"Repository '{repo_name}' deleted successfully",
        "repo_name": repo_name,
        "deleted_paths": deleted_paths,
        "missing_paths": missing_paths,
    }


def _run_ingestion(repo_url: str, repo_name: Optional[str]):
    """Background ingestion task."""
    try:
        _ingestion_status[repo_url] = {"status": "running", "message": "Ingestion in progress..."}
        from ingestion.ingest import ingest_repo
        ingest_repo(repo_url, repo_name=repo_name)
        # Clear cache for this repo so fresh data is loaded
        final_name = repo_name or repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        clear_repo_cache(final_name)
        _ingestion_status[repo_url] = {"status": "complete", "message": "Ingestion complete", "repo_name": final_name}
    except Exception as e:
        _ingestion_status[repo_url] = {"status": "failed", "message": str(e), "traceback": traceback.format_exc()}


@router.post("/ingest")
def ingest_repo_endpoint(request: IngestRequest, background_tasks: BackgroundTasks):
    """Start repository ingestion (runs in background)."""
    _ingestion_status[request.repo_url] = {"status": "queued", "message": "Starting ingestion..."}
    background_tasks.add_task(_run_ingestion, request.repo_url, request.repo_name)
    return {"message": "Ingestion started", "repo_url": request.repo_url, "status": "queued"}


@router.get("/ingest/status")
def get_ingestion_status(repo_url: str):
    """Check ingestion status for a repo URL."""
    status = _ingestion_status.get(repo_url)
    if not status:
        return {"status": "unknown", "message": "No ingestion found for this URL"}
    return status
