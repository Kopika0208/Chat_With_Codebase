"""
FastAPI backend for CodeExplorer.
Wraps existing ingestion, retrieval, and analysis pipeline as REST endpoints.

Run with:
    cd <project_root>
    uvicorn backend.main:app --reload --port 8000
"""

import os
import sys

# Ensure project root is in path for all imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Also add retrieval/ to path for graph_rag imports
RETRIEVAL_DIR = os.path.join(PROJECT_ROOT, "retrieval")
if RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, RETRIEVAL_DIR)

from dotenv import load_dotenv
load_dotenv()


def _disable_langsmith_tracing():
    """Disable LangSmith tracing for this process to avoid quota errors."""
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_TRACING"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    for key in (
        "LANGCHAIN_API_KEY",
        "LANGCHAIN_ENDPOINT",
        "LANGCHAIN_LLM_ENDPOINT",
        "LANGCHAIN_LIVE_CHAT_API_KEY",
        "LANGSMITH_API_KEY",
        "LANGSMITH_ENDPOINT",
    ):
        os.environ.pop(key, None)


_disable_langsmith_tracing()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import repos, query, callgraph, health, contributions, onboarding

# ======================================================
# 🚀 APP SETUP
# ======================================================

app = FastAPI(
    title="CodeExplorer API",
    description="AI-powered codebase analysis - ingestion, retrieval, health, and onboarding",
    version="1.0.0",
)

# CORS - allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://repo-mind-ten.vercel.app/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# 📡 REGISTER ROUTERS
# ======================================================

app.include_router(repos.router)
app.include_router(query.router)
app.include_router(callgraph.router)
app.include_router(health.router)
app.include_router(contributions.router)
app.include_router(onboarding.router)


# ======================================================
# 🏠 ROOT
# ======================================================

@app.get("/")
def root():
    return {
        "service": "CodeExplorer API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "repos": "/api/repos",
            "query": "/api/repos/{repo_name}/query",
            "callgraph": "/api/repos/{repo_name}/callgraph",
            "health": "/api/repos/{repo_name}/health",
            "contributions": "/api/repos/{repo_name}/contributions",
            "onboarding": "/api/repos/{repo_name}/onboarding/overview",
        },
    }


@app.get("/api/health")
def api_health():
    """API health check."""
    from backend.deps import list_repos
    return {
        "status": "ok",
        "repos_available": len(list_repos()),
    }
