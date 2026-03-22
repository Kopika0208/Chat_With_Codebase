"""Query pipeline endpoint - Graph-RAG retrieval + LLM answer."""

import os
import sys
import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.deps import (
    list_repos, get_vectorstore, get_llm, get_graph_rag_retriever,
    load_call_graph, load_symbol_table, load_knowledge_graph,
    load_boot_chain, load_core_structures, load_async_patterns,
)

router = APIRouter(prefix="/api/repos/{repo_name}", tags=["query"])

# LLM prompt template
ANSWER_PROMPT = """
You are an expert assistant helping a developer understand a codebase.

You are given several code context chunks from a repository and a user question.

<context>
{context}
</context>

Sources (file and line ranges):
{sources}

Question: {input}

Respond with:

- **Summary:** Short, precise technical answer.
- **Explanation:** Step-by-step reasoning in simple language.
- **Where in the code:** Mention the most relevant files and line ranges.
- **Navigation Tips:** Which files/functions to open first and why.

If you are uncertain or the context is insufficient, clearly say so.
"""

STARTUP_PROMPT = """
You are an expert assistant helping a developer understand application startup behavior.

<boot_chain>
{boot_chain}
</boot_chain>

Question: {input}

Respond with:
- **Entry Point:** The most likely startup function(s) and file locations.
- **Startup Lifecycle:** Ordered explanation from boot to ready.
- **Where to Inspect:** The most relevant files/functions to open first.
"""


class QueryRequest(BaseModel):
    query: str
    max_depth: int = 2
    strategy: str = "dfs"
    k_initial: int = 5


class DocResult(BaseModel):
    path: str
    symbol_name: str
    start_line: int
    end_line: int
    language: str
    content: str


class QueryResponse(BaseModel):
    answer: str
    query: str
    method: str
    latency_seconds: float
    docs: List[DocResult]
    graph_stats: Optional[dict] = None


def _is_startup_query(query: str) -> bool:
    """Detect if query is about application startup/entry points."""
    q = query.lower()
    return any(term in q for term in [
        "startup", "boot", "entry point", "main function",
        "how does it start", "initialization", "ready state",
        "lifecycle", "how does the app run", "how to run",
    ])


def _format_boot_chain(boot_chain: dict) -> str:
    """Format boot chain for LLM prompt."""
    if not boot_chain:
        return "No boot-chain metadata available."
    lines = [boot_chain.get("summary", "")]
    for step in boot_chain.get("ordered_steps", [])[:20]:
        parent = step.get("called_by") or "ROOT"
        lines.append(
            f"- depth={step.get('depth', '?')} {parent} -> {step.get('name')} "
            f"({step.get('file')}:{step.get('line', '?')})"
        )
    return "\n".join(l for l in lines if l)


def _doc_to_result(doc) -> DocResult:
    """Convert a langchain Document to API response format."""
    meta = doc.metadata or {}
    raw_path = meta.get("path", "unknown")
    clean_path = raw_path.split(":", 1)[1] if ":" in raw_path else raw_path

    symbol_name = meta.get("symbol_name")
    if symbol_name is None:
        symbol_name = ""
    elif not isinstance(symbol_name, str):
        symbol_name = str(symbol_name)

    path = clean_path
    if path is None:
        path = ""

    language = meta.get("language")
    if language is None:
        language = ""
    elif not isinstance(language, str):
        language = str(language)

    return DocResult(
        path=path,
        symbol_name=symbol_name,
        start_line=int(meta.get("start_line", 0) or 0),
        end_line=int(meta.get("end_line", 0) or 0),
        language=language,
        content=(doc.page_content or "")[:2000],
    )


@router.post("/query")
def run_query(repo_name: str, request: QueryRequest):
    """Execute Graph-RAG query pipeline and return answer with sources."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    start_time = time.time()
    query = request.query
    method = "graph_rag"

    try:
        # Check for startup queries
        if _is_startup_query(query):
            boot_chain = load_boot_chain(repo_name)
            if boot_chain and boot_chain.get("ordered_steps"):
                method = "startup"
                context = _format_boot_chain(boot_chain)
                llm = get_llm()
                prompt = STARTUP_PROMPT.format(boot_chain=context, input=query)
                response = llm.invoke(prompt)
                return QueryResponse(
                    answer=response.content.strip(),
                    query=query,
                    method=method,
                    latency_seconds=round(time.time() - start_time, 3),
                    docs=[],
                )

        # Standard Graph-RAG pipeline
        retriever = get_graph_rag_retriever(repo_name)
        if not retriever:
            # Fallback to simple vector search
            method = "vector"
            vectorstore = get_vectorstore(repo_name)
            if not vectorstore:
                raise HTTPException(status_code=500, detail="No vectorstore or Graph-RAG retriever available")
            docs = vectorstore.similarity_search(query, k=request.k_initial)
            final_docs = docs
            graph_stats = None
        else:
            # Full Graph-RAG retrieval
            result = retriever.retrieve(
                query=query,
                k_initial=request.k_initial,
                max_depth=request.max_depth,
                strategy=request.strategy,
                edge_types=["calls", "called_by", "contains", "dataflow"],
                deduplicate=True,
            )
            final_docs = result.final_documents
            graph_stats = result.statistics

        if not final_docs:
            return QueryResponse(
                answer="No relevant code found for this query. Try rephrasing your question.",
                query=query,
                method=method,
                latency_seconds=round(time.time() - start_time, 3),
                docs=[],
                graph_stats=graph_stats,
            )

        # Build context for LLM
        context_parts = []
        source_lines = []
        for i, doc in enumerate(final_docs[:10], 1):
            meta = doc.metadata or {}
            path = meta.get("path", "unknown")
            symbol = meta.get("symbol_name", "")
            start = meta.get("start_line", "?")
            end = meta.get("end_line", "?")
            context_parts.append(f"### Source {i}: {path}:{symbol} ({start}-{end})\n{doc.page_content}")
            source_lines.append(f"{i}. {path}: {start}-{end}")

        context_str = "\n\n---\n\n".join(context_parts)
        sources_str = "\n".join(source_lines)

        # Get LLM answer
        llm = get_llm()
        prompt = ANSWER_PROMPT.format(context=context_str, sources=sources_str, input=query)
        response = llm.invoke(prompt)

        latency = round(time.time() - start_time, 3)

        # Save retrieval metrics if evaluation module is available
        try:
            from evaluation.collector import save_retrieval_metrics
            unique_files = set()
            unique_symbols = set()
            languages = set()
            for doc in final_docs:
                m = doc.metadata or {}
                if m.get("path"):
                    unique_files.add(m["path"])
                if m.get("symbol_name"):
                    unique_symbols.add(m["symbol_name"])
                if m.get("language"):
                    languages.add(m["language"])

            save_retrieval_metrics(
                repo_name=repo_name,
                query=query,
                method=method,
                latency_seconds=latency,
                docs_returned=len(final_docs),
                unique_files=len(unique_files),
                unique_symbols=len(unique_symbols),
                unique_languages=sorted(languages),
                answer_length_chars=len(response.content),
                answer_length_words=len(response.content.split()),
                has_code_blocks="```" in response.content,
                anchor_nodes=graph_stats.get("anchor_nodes", 0) if graph_stats else 0,
                total_visited=graph_stats.get("total_nodes_visited", 0) if graph_stats else 0,
                max_depth=graph_stats.get("max_depth_reached", 0) if graph_stats else 0,
                edges_traversed=graph_stats.get("edges_traversed", 0) if graph_stats else 0,
            )
        except Exception:
            pass

        return QueryResponse(
            answer=response.content.strip(),
            query=query,
            method=method,
            latency_seconds=latency,
            docs=[_doc_to_result(d) for d in final_docs[:10]],
            graph_stats=graph_stats,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
