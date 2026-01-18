# retrieval.py
"""
Core retrieval functions combining vector search, hybrid reranking, and multi-hop logic.
"""

import re
import numpy as np
from typing import List, Tuple, Dict, Optional
from langchain_core.documents import Document
from cache import get_vectorstore, get_embeddings


def infer_metadata_filters_from_query(query: str) -> Dict:
    """Infer metadata filters from query terms."""
    q = query.lower()
    filters = {}

    lang_map = {
        "python": "python",
        "py": "python",
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "typescript",
        "ts": "typescript",
        "java": "java",
        "c++": "cpp",
        "cpp": "cpp",
        "rust": "rust",
        "go": "go",
    }
    for k, v in lang_map.items():
        if k in q:
            filters["language"] = v

    if "function" in q or "def " in q:
        filters["node_type"] = "function_definition"
    if "class" in q:
        filters["node_type"] = "class_definition"

    file_hits = re.findall(r"\w+\.(py|js|ts|java|cpp|c|rs|go)", q)
    if file_hits:
        filters["path"] = {"$contains": file_hits[0]}

    print("🧠 Implicit Filters:", filters if filters else "{}")
    return filters


def stage1_vector_search(query: str, k: int = 16) -> List[Tuple[Document, float]]:
    """Retriever 1: plain vector search (no filters)."""
    vectorstore = get_vectorstore()
    docs_and_scores = vectorstore.similarity_search_with_score(query, k=k)
    print(
        f"🔎 Stage 1 – Vector search retrieved {len(docs_and_scores)} chunks for query: {query!r}"
    )
    return docs_and_scores


def hybrid_rerank(query: str, docs_and_scores: List[Tuple[Document, float]], 
                  inferred_filters: Dict, top_k: int = 6) -> List[Document]:
    """
    Hybrid reranking combining vector similarity, metadata, symbols, and path weighting.
    """
    if not docs_and_scores:
        return []

    embeddings = get_embeddings()
    q_tokens = set(re.findall(r"[a-zA-Z_]\w*", query.lower()))
    
    try:
        q_vec = embeddings.embed_query(query)
        q_vec = np.array(q_vec, dtype=float)
        q_norm = np.linalg.norm(q_vec) + 1e-8
    except Exception:
        q_vec, q_norm = None, None

    reranked = []

    for doc, dist in docs_and_scores:
        meta = doc.metadata or {}

        # 1) Base similarity from FAISS distance
        base_sim = 1.0 / (1.0 + float(dist))
        score = base_sim

        # 2) Metadata matches
        lang_filter = inferred_filters.get("language")
        if lang_filter and (meta.get("language") or "").lower() == lang_filter:
            score += 0.4

        node_filter = inferred_filters.get("node_type")
        if node_filter and (meta.get("node_type") or "").lower() == node_filter:
            score += 0.3

        path_filter = (
            inferred_filters.get("path", {}).get("$contains", "").lower()
            if inferred_filters.get("path")
            else ""
        )
        path = (meta.get("path") or "").lower()
        if path_filter and path_filter in path:
            score += 0.3

        # 3) Symbol / parent_class in query
        symbol = (meta.get("symbol_name") or "").lower()
        if symbol and symbol in query.lower():
            score += 0.6

        parent = (meta.get("parent_class") or "").lower()
        if parent and parent in query.lower():
            score += 0.4

        # 4) Code heuristics
        text_head = (doc.page_content or "")[:400].lower()
        full_text = doc.page_content or ""

        if "def " in full_text or "function " in full_text:
            score += 0.2
        if "class " in full_text:
            score += 0.2
        if "import " in text_head:
            score += 0.15
        if "todo" in full_text.lower() or "fixme" in full_text.lower():
            score += 0.05

        # Keywords from query in path
        if any(t in path for t in q_tokens):
            score += 0.2

        # Path weighting (for MVC-ish repos)
        if any(seg in path for seg in ["views", "controllers", "routes", "api"]):
            score += 0.25
        if any(seg in path for seg in ["models", "schemas"]):
            score += 0.2
        if any(seg in path for seg in ["utils", "helpers", "lib"]):
            score += 0.15

        # 5) Cosine similarity using embeddings
        if q_vec is not None:
            try:
                d_vec = embeddings.embed_query(full_text[:1000])
                d_vec = np.array(d_vec, dtype=float)
                d_norm = np.linalg.norm(d_vec) + 1e-8
                cosine = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))
                score += 0.5 * cosine
            except Exception:
                pass

        reranked.append((doc, score))

    reranked.sort(key=lambda x: x[1], reverse=True)
    top_docs = [d for d, _ in reranked[:top_k]]
    print(
        "📊 Hybrid rerank top paths:",
        [(d.metadata.get("path"), s) for d, s in reranked[:top_k]],
    )
    return top_docs


def deduplicate_docs(docs: List[Document], semantic: bool = True, 
                    threshold: float = 0.9) -> List[Document]:
    """Remove duplicate chunks based on exact + optional semantic similarity."""
    if not docs:
        return docs

    embeddings = get_embeddings()
    unique = []
    seen_keys = set()
    seen_vecs = []

    for d in docs:
        m = d.metadata or {}
        key = (m.get("path"), m.get("start_line"), m.get("end_line"))
        if key in seen_keys:
            continue

        is_duplicate = False
        if semantic:
            try:
                snippet = (d.page_content or "")[:800]
                vec = embeddings.embed_query(snippet)
                v = np.array(vec, dtype=float)
                v_norm = np.linalg.norm(v) + 1e-8

                for prev_v in seen_vecs:
                    prev_norm = np.linalg.norm(prev_v) + 1e-8
                    cosine = float(np.dot(v, prev_v) / (v_norm * prev_norm))
                    if cosine > threshold:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_vecs.append(v)
            except Exception:
                pass

        if not is_duplicate:
            seen_keys.add(key)
            unique.append(d)

    if len(unique) < len(docs):
        print(f"🧹 Deduplicated {len(docs)} → {len(unique)} chunks")
    return unique


def get_expanded_context(docs: List[Document], repo_path: str, 
                        window: int = 20) -> Dict[int, str]:
    """Expand each doc with surrounding lines without mutating Document objects."""
    import os
    
    expanded_map = {}

    for doc in docs:
        meta = doc.metadata or {}
        expanded_context = ""
        try:
            file_path = os.path.join(repo_path, meta["path"])
            if not os.path.exists(file_path):
                expanded_map[id(doc)] = ""
                continue

            start, end = meta.get("start_line", 1), meta.get("end_line", 1)
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            context_start = max(0, start - window)
            context_end = min(len(lines), end + window)
            expanded_context = "".join(lines[context_start:context_end])
        except Exception:
            expanded_context = ""

        expanded_map[id(doc)] = expanded_context

    return expanded_map


def build_context_and_sources(docs: List[Document], expanded_map: Dict[int, str],
                             max_chars_per_doc: int = 1200) -> Tuple[str, str]:
    """Merge chunks + expanded context and build a sources string."""
    context_parts = []
    source_lines = []

    for i, d in enumerate(docs, start=1):
        m = d.metadata or {}
        path = (m.get("path") or "unknown").replace("\\", "/")
        start = m.get("start_line", "?")
        end = m.get("end_line", "?")
        header = f"### Source {i}: {path} ({start}–{end})"

        chunk_text = d.page_content or ""
        expanded = expanded_map.get(id(d), "") or ""

        merged = chunk_text + "\n\n# Additional Context\n" + expanded
        merged = merged[:max_chars_per_doc]

        context_parts.append(header + "\n" + merged)
        source_lines.append(f"{i}. {path}: {start}–{end}")

    context_str = "\n\n-----\n\n".join(context_parts)
    sources_str = "\n".join(source_lines) if source_lines else "None"
    return context_str, sources_str


def build_followup_queries(original_query: str, seed_docs: List[Document],
                          max_queries: int = 3) -> List[str]:
    """Build simple follow-up queries from top docs."""
    import os
    
    followups = set()

    for d in seed_docs:
        m = d.metadata or {}
        path = (m.get("path") or "").replace("\\", "/")
        symbol = (m.get("symbol_name") or "").strip()
        parent = (m.get("parent_class") or "").strip()

        filename = os.path.basename(path)
        module, _ = os.path.splitext(filename)
        directory = os.path.dirname(path).split("/")[-1] if "/" in path else ""

        if symbol:
            followups.add(f"{symbol} implementation in {filename}")
            followups.add(f"{symbol} usage {module}")

        if parent:
            followups.add(f"{parent} class methods in {filename}")
            followups.add(f"{parent} initialization {module}")

        if module:
            followups.add(f"{module} logic {symbol or parent}")
        if directory:
            followups.add(f"{directory} {symbol or parent} flow")

        imports = m.get("imports") or []
        if isinstance(imports, list):
            for imp in imports[:3]:
                imp_name_match = re.findall(
                    r"from\s+([\w\.]+)\s+import|import\s+([\w\.]+)", imp
                )
                for g1, g2 in imp_name_match:
                    imp_name = g1 or g2
                    if imp_name:
                        followups.add(f"uses {imp_name}")

    cleaned = []
    for q in followups:
        q_clean = " ".join(q.split())
        if len(q_clean) > 3 and len(q_clean.split()) <= 12:
            cleaned.append(q_clean)

    cleaned = list(dict.fromkeys(cleaned))
    trimmed = cleaned[:max_queries]
    print("🔁 Multi-hop follow-up queries:", trimmed)
    return trimmed


def multi_hop_retrieve(query: str, inferred_filters: Dict, hops: int = 2,
                      base_k: int = 16, top_k: int = 6) -> List[Document]:
    """Two-hop retrieval: vector search + hybrid rerank, then follow-up queries."""
    hop1_scores = stage1_vector_search(query, k=base_k)
    hop1_docs = hybrid_rerank(query, hop1_scores, inferred_filters, top_k=top_k)

    if hops <= 1 or not hop1_docs:
        return hop1_docs

    followup_queries = build_followup_queries(query, hop1_docs, max_queries=3)
    if not followup_queries:
        print("🔁 Multi-hop: no follow-up queries generated; returning hop1 docs.")
        return hop1_docs

    all_scores = list(hop1_scores)
    for fq in followup_queries:
        hop2_scores = stage1_vector_search(fq, k=12)
        all_scores.extend(hop2_scores)

    combined_docs = hybrid_rerank(query, all_scores, inferred_filters, top_k=top_k)
    combined_docs = deduplicate_docs(combined_docs, semantic=False)
    print(
        f"🔁 Multi-hop: combined {len(all_scores)} candidates → {len(combined_docs)} docs after rerank+dedup."
    )
    return combined_docs


def matched_terms_in_chunk(query: str, doc: Document) -> List[str]:
    """Find matched query terms in document."""
    q_tokens = set(re.findall(r"[a-zA-Z_]\w*", query.lower()))
    text_tokens = set(re.findall(r"[a-zA-Z_]\w*", (doc.page_content or "").lower()))
    common = sorted(q_tokens.intersection(text_tokens))
    return common[:10]
