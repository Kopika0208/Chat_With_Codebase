"""Code health analysis endpoint."""

import os
import sys
from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.deps import (
    list_repos, load_call_graph, load_symbol_table, load_health,
    get_repo_source_path, get_repo_paths,
)
from backend.health_analysis import compute_health_payload
from redis_storage import save_json

router = APIRouter(prefix="/api/repos/{repo_name}", tags=["health"])


@router.get("/health")
def get_health(repo_name: str):
    """
    Run code health analysis and return scores, smells, and suggestions.
    Uses the same pipeline as the Streamlit Code Health tab.
    """
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    cached_health = load_health(repo_name)
    if cached_health:
        return cached_health

    call_graph = load_call_graph(repo_name)
    symbol_table = load_symbol_table(repo_name)
    repo_path = get_repo_source_path(repo_name)

    try:
        payload = compute_health_payload(repo_path, call_graph, symbol_table)
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Code health modules not available: {e}")

    try:
        save_json(repo_name, "code_health", payload)
    except Exception:
        pass

    return payload
