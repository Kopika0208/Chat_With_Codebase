# ingestion/__init__.py - Package initialization for ingestion modules

from .ingest import (
    ingest_repo,
    VECTOR_DIR,
    CALLGRAPH_PATH,
    TARGET_REPO_DIR,
    EXTENSIONS,
    EMBED_MODEL,
    PROJECT_ROOT,
)

__all__ = [
    'ingest_repo',
    'VECTOR_DIR',
    'CALLGRAPH_PATH',
    'TARGET_REPO_DIR',
    'EXTENSIONS',
    'EMBED_MODEL',
    'PROJECT_ROOT',
]
