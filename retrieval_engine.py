# retrieval_engine.py
import os
import re
from typing import List, Dict, Any
from langchain_core.documents import Document

# ======================================================
# 🔍 IMPLICIT METADATA FILTERING
# ======================================================
def infer_metadata_filters(query: str) -> Dict[str, Any]:
    q = query.lower()
    filters = {}

    lang_map = {
        "python": "python", "py": "python",
        "javascript": "javascript", "js": "javascript",
        "typescript": "typescript", "ts": "typescript",
        "java": "java",
        "c++": "cpp", "cpp": "cpp",
        "rust": "rust",
        "go": "go",
    }
    for k, v in lang_map.items():
        if k in q:
            filters["language"] = v

    if "function" in q:
        filters["node_type"] = "function_definition"
    if "class" in q:
        filters["node_type"] = "class_definition"

    file_keywords = re.findall(r"\w+\.(py|js|ts|java|cpp|c|rs)", q)
    if file_keywords:
        filters["path"] = {"$contains": file_keywords[0]}

    return filters


# ======================================================
# 🧠 QUERY REWRITING
# ======================================================
def rewrite_query(llm, query: str) -> str:
    prompt = f"""
Rewrite the user query into a clearer technical query for code retrieval.

User query: {query}
Rewritten:
"""
    result = llm.invoke(prompt)
    return result.text.strip()


# ======================================================
# 🔁 MULTI-HOP RETRIEVAL
# ======================================================
def multihop_query_generation(llm, query: str):
    prompt = f"""
Break this question into 1–3 retrieval sub-queries.

Question: {query}

Subqueries:
"""
    result = llm.invoke(prompt)
    subs = [x.strip("-• ").strip() for x in result.text.split("\n") if len(x.strip()) > 2]
    return subs or [query]


# ======================================================
# 🧰 CONTEXT EXPANSION
# ======================================================
def expand_context(docs, repo_path, window=25):
    expanded = []
    for doc in docs:
        meta = doc.metadata
        file_path = os.path.join(repo_path, meta.get("path", ""))

        if not os.path.exists(file_path):
            expanded.append(doc)
            continue

        try:
            start = meta.get("start_line", 1)
            end = meta.get("end_line", start)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            s = max(0, start - window)
            e = min(len(lines), end + window)

            ctx = "".join(lines[s:e])
            doc.page_content += f"\n\n# Expanded Context ({s}-{e})\n{ctx}"
        except:
            pass

        expanded.append(doc)
    return expanded


# ======================================================
# 🔀 HYBRID RERANKING
# ======================================================
def hybrid_rerank(query: str, docs: List[Document], scores: List[float]):
    ranked = []
    q = query.lower()

    for doc, score in zip(docs, scores):
        text = doc.page_content.lower()
        keyword_hits = sum(1 for w in q.split() if w in text)
        hybrid_score = (0.7 * score) + (0.3 * keyword_hits)
        ranked.append((doc, hybrid_score))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return [d for d, _ in ranked]


# ======================================================
# 🧠 LLM RERANKING
# ======================================================
def llm_rerank(llm, query: str, docs: List[Document]):
    prompt = f"""
Rank these snippets by relevance to the query:

Query: {query}

Snippets:
"""
    for i, doc in enumerate(docs):
        prompt += f"\nSnippet {i+1}:\n{doc.page_content}\n"

    prompt += "\nReturn only: comma-separated snippet numbers in best order."

    result = llm.invoke(prompt)
    nums = re.findall(r"\d+", result.text)

    try:
        order = [int(n) - 1 for n in nums]
        return [docs[i] for i in order if 0 <= i < len(docs)]
    except:
        return docs


# ======================================================
# 🧼 DEDUPLICATION
# ======================================================
def dedupe_docs(docs):
    seen = set()
    unique = []

    for d in docs:
        meta = d.metadata
        key = (meta.get("path"), meta.get("symbol_name") or "")

        if key in seen:
            continue

        seen.add(key)
        unique.append(d)

    return unique
