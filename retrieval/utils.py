# utils.py
"""
Utility functions for code display, formatting, and UI helpers.
"""

import os
import re


def rewrite_query_if_enabled(query: str, enabled: bool) -> str:
    """Rewrite query using LLM for better retrieval."""
    if not enabled:
        return query
    
    from cache import get_llm
    
    QUERY_REWRITE_PROMPT = """
You are a helpful assistant that rewrites queries for code search.

Given this user question about a codebase:

"{query}"

Rewrite it as a concise search query that:
- Keeps important function, class, variable, and file names
- Includes key technical terms
- Removes filler words and conversational phrasing

Respond with ONLY the rewritten query text, nothing else.
"""
    
    try:
        llm = get_llm()
        msg = QUERY_REWRITE_PROMPT.format(query=query)
        resp = llm.invoke(msg)
        rewritten = resp.content.strip()
        if not rewritten or len(rewritten) < 3:
            return query
        print(f"✏️ Query rewritten:\n  Original: {query}\n  Rewritten: {rewritten}")
        return rewritten
    except Exception as e:
        print(f"⚠️ Query rewriting failed: {e}")
        return query


def summarize_chunk_heuristic(doc) -> str:
    """Lightweight heuristic summary of code chunk."""
    text = doc.page_content or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "Code chunk with no visible content."

    # Prefer docstring-like or comment lines
    for ln in lines:
        if ln.startswith('"""') or ln.startswith("'''") or ln.startswith("#"):
            return (
                ln.strip("# ")
                .strip()
                .strip('"""')
                .strip("'''")
                .strip()
            )

    # Fallback: first non-empty line
    return lines[0][:120]


def chunk_title(doc) -> str:
    """Generate title for a code chunk."""
    m = doc.metadata or {}
    path = (m.get("path") or "unknown").replace("\\", "/")
    symbol = m.get("symbol_name")
    node_type = m.get("node_type") or "chunk"
    if symbol:
        return f"{path} → {symbol}"
    return f"{path} → {node_type}"


def breadcrumb_for_path(path: str) -> str:
    """Convert file path to breadcrumb format."""
    parts = path.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return path
    return " › ".join(parts)


def load_file_segment(meta: dict, repo_path: str, padding: int = 20):
    """Load surrounding code context for a chunk."""
    try:
        file_path = os.path.join(repo_path, meta["path"])
        if not os.path.exists(file_path):
            return None
        start, end = meta.get("start_line", 1), meta.get("end_line", 1)
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        s = max(0, start - padding)
        e = min(len(lines), end + padding)
        segment = "".join(lines[s:e])
        return segment, s + 1, e
    except Exception:
        return None
