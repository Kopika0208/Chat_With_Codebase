# ingestion/__init__.py - Package initialization for ingestion modules

# Try to import constants first, with fallback definitions if import fails
try:
    from .ingest import (
        ingest_repo,
        ingest_repos,
        EXTENSIONS,
        EMBED_MODEL,
        PROJECT_ROOT,
        VECTOR_DIR,
        CALLGRAPH_PATH,
        TARGET_REPO_DIR,
        _get_repo_paths,
    )
    from .api_ingestion import ingest_repo_via_api
    from .incremental_update import update_repo_via_api
except ImportError:
    # Fallback: Define constants directly if import fails
    import os
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    VECTOR_DIR = os.path.join(_project_root, "data", "vector_store")
    CALLGRAPH_PATH = os.path.join(_project_root, "data", "call_graph.json")
    TARGET_REPO_DIR = os.path.join(_project_root, "repos", "myrepo")
    PROJECT_ROOT = _project_root
    EXTENSIONS = ('.py', '.js', '.java', '.ts', '.md', '.txt', '.go', '.cpp', '.c', '.h', '.rs')
    EMBED_MODEL = "voyage-code-3"
    # Functions will be None if import fails
    ingest_repo = None
    ingest_repos = None
    ingest_repo_via_api = None
    update_repo_via_api = None
    _get_repo_paths = None

__all__ = [
    'ingest_repo',
    'ingest_repos',
    'ingest_repo_via_api',
    'update_repo_via_api',
    'EXTENSIONS',
    'EMBED_MODEL',
    'PROJECT_ROOT',
    'VECTOR_DIR',
    'CALLGRAPH_PATH',
    'TARGET_REPO_DIR',
    '_get_repo_paths',
]
