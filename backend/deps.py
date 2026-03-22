"""
Non-Streamlit data loading and caching layer.
Replaces retrieval/cache.py for use outside Streamlit (FastAPI, scripts, etc).
All expensive loads are cached in memory per repo.
"""

import os
import json
import sys
from functools import lru_cache
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
EMBED_MODEL = "mixedbread-ai/mxbai-embed-large-v1"


# ======================================================
# 📂 REPO DISCOVERY
# ======================================================

def list_repos() -> List[str]:
    """List all ingested repositories."""
    if not os.path.exists(DATA_DIR):
        return []
    return sorted(
        d for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d))
    )


def get_repo_paths(repo_name: str) -> Dict[str, str]:
    """Get all data file paths for a repo."""
    base = os.path.join(DATA_DIR, repo_name)
    return {
        "base": base,
        "vector": os.path.join(base, "vector_store"),
        "callgraph": os.path.join(base, "call_graph.json"),
        "health": os.path.join(base, "code_health.json"),
        "bootchain": os.path.join(base, "boot_chain.json"),
        "corestructures": os.path.join(base, "core_structures.json"),
        "knowledge": os.path.join(base, "knowledge_graph.json"),
        "symbol": os.path.join(base, "symbol_table.json"),
        "dataflow": os.path.join(base, "dataflow_analysis.json"),
        "asyncpatterns": os.path.join(base, "async_patterns.json"),
        "contributions": os.path.join(base, "contributions.json"),
        "documentation": os.path.join(base, "documentation.json"),
        "api_source": os.path.join(base, "api_source"),
    }


def get_repo_source_path(repo_name: str) -> str:
    """Resolve best available source file path for a repo."""
    git_path = os.path.join(PROJECT_ROOT, "repos", repo_name)
    if os.path.isdir(git_path):
        return git_path
    api_source = os.path.join(DATA_DIR, repo_name, "api_source")
    if os.path.isdir(api_source):
        return api_source
    return os.path.join(DATA_DIR, repo_name)


# ======================================================
# 📊 JSON DATA LOADERS (cached in memory)
# ======================================================

_json_cache: Dict[str, Any] = {}


def _load_json(path: str) -> Any:
    """Load JSON file with caching."""
    if path in _json_cache:
        return _json_cache[path]
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _json_cache[path] = data
        return data
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}")
        return {}


def clear_repo_cache(repo_name: str):
    """Clear all cached data for a repo (call after re-ingestion)."""
    paths = get_repo_paths(repo_name)
    keys_to_remove = [k for k in _json_cache if any(k.startswith(p) for p in paths.values())]
    for k in keys_to_remove:
        _json_cache.pop(k, None)
    # Also clear lru_cache entries
    get_embeddings.cache_clear()
    _get_vectorstore_cached.cache_clear()
    _get_graph_rag_retriever_cached.cache_clear()


def load_call_graph(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["callgraph"])


def load_health(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["health"])


def load_symbol_table(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["symbol"])


def load_knowledge_graph(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["knowledge"])


def load_boot_chain(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["bootchain"])


def load_core_structures(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["corestructures"])


def load_dataflow(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["dataflow"])


def load_async_patterns(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["asyncpatterns"])


def load_contributions(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["contributions"])


def load_documentation(repo_name: str) -> Dict:
    return _load_json(get_repo_paths(repo_name)["documentation"])


# ======================================================
# 🔢 EMBEDDINGS & VECTORSTORE
# ======================================================

@lru_cache(maxsize=1)
def get_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


@lru_cache(maxsize=8)
def _get_vectorstore_cached(repo_name: str):
    from langchain_community.vectorstores import FAISS
    paths = get_repo_paths(repo_name)
    vector_path = paths["vector"]
    if not os.path.exists(vector_path):
        return None
    embeddings = get_embeddings()
    return FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)


def get_vectorstore(repo_name: str):
    return _get_vectorstore_cached(repo_name)


# ======================================================
# 🤖 LLM
# ======================================================

@lru_cache(maxsize=1)
def get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model="llama-3.1-8b-instant", temperature=0)


# ======================================================
# 🔗 GRAPH-RAG RETRIEVER
# ======================================================

@lru_cache(maxsize=8)
def _get_graph_rag_retriever_cached(repo_name: str):
    try:
        paths = get_repo_paths(repo_name)
        vectorstore = get_vectorstore(repo_name)
        if not vectorstore or not os.path.exists(paths["knowledge"]):
            return None

        # Import graph_rag from retrieval package
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "retrieval"))
        from graph_rag import create_graph_rag_retriever

        all_documents = list(vectorstore.docstore._dict.values())
        return create_graph_rag_retriever(
            vectorstore=vectorstore,
            knowledge_graph_path=paths["knowledge"],
            documents=all_documents,
            repo_name=repo_name,
        )
    except Exception as e:
        print(f"[GraphRAG] Failed for {repo_name}: {e}")
        return None


def get_graph_rag_retriever(repo_name: str):
    return _get_graph_rag_retriever_cached(repo_name)


# ======================================================
# 📊 REPO SUMMARY STATS
# ======================================================

def get_repo_summary(repo_name: str) -> Dict:
    """Get quick summary stats for a repo from its data files."""
    paths = get_repo_paths(repo_name)
    summary = {
        "name": repo_name,
        "status": "Indexed",
        "files": 0,
        "functions": 0,
        "classes": 0,
        "loc": 0,
        "languages": [],
        "has_callgraph": os.path.exists(paths["callgraph"]),
        "has_knowledge_graph": os.path.exists(paths["knowledge"]),
        "has_contributions": os.path.exists(paths["contributions"]),
        "has_vectorstore": os.path.exists(paths["vector"]),
    }

    # Extract stats from symbol table
    symbol_table = load_symbol_table(repo_name)
    file_symbols = symbol_table.get("file_symbols", {})
    global_index = symbol_table.get("global_index", {})

    if file_symbols:
        summary["files"] = len(file_symbols)
        lang_counts = {}
        for file_key, file_data in file_symbols.items():
            if isinstance(file_data, dict):
                symbols = file_data.get("symbols", {})
                for sym in symbols.values():
                    if isinstance(sym, dict):
                        kind = sym.get("kind", "")
                        if kind in ("function", "method"):
                            summary["functions"] += 1
                        elif kind == "class":
                            summary["classes"] += 1
                # Detect language from extension
                ext = os.path.splitext(file_key.split(":")[-1])[1].lower()
                lang_map = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
                            ".java": "Java", ".go": "Go", ".rs": "Rust",
                            ".cpp": "C++", ".c": "C", ".h": "C"}
                lang = lang_map.get(ext)
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

        summary["languages"] = sorted(lang_counts.keys(), key=lambda l: -lang_counts[l])
    elif global_index:
        file_list = global_index.get("files", [])
        summary["files"] = len(file_list)

    # Get LOC estimate from knowledge graph or vectorstore
    kg = load_knowledge_graph(repo_name)
    if kg:
        nodes = kg.get("nodes", {})
        if isinstance(nodes, dict):
            for node in nodes.values():
                if isinstance(node, dict):
                    line = node.get("line_number", 0) or node.get("line", 0)
                    summary["loc"] = max(summary["loc"], int(line) if line else 0)

    return summary
