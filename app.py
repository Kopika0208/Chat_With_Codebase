# app.py
import os
import re
import json
import traceback
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from pyvis.network import Network
import networkx as nx

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client

from ingest import ingest_repo, VECTOR_DIR, CALLGRAPH_PATH

# ===============================
# ⚙️ SETUP
# ===============================
load_dotenv()
st.set_page_config(page_title="Chat with Your Codebase", layout="wide")
st.title("💬 Chat with Your Codebase – Multi-Hop + Call Graph Visualization (Optimized)")

LANGCHAIN_PROJECT = "chat-with-codebase"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT

try:
    client = Client()
    print(f"✅ LangSmith connected: {client.api_url}")
except Exception:
    print("⚠️ LangSmith inactive")

EMBED_MODEL = "thenlper/gte-base"
DEFAULT_REPO_PATH = "repos/myrepo"


# ===============================
# 🧠 CACHED HEAVY RESOURCES
# ===============================
@st.cache_resource(show_spinner=False)
def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


@st.cache_resource(show_spinner=False)
def get_vectorstore():
    embeddings = get_embeddings()
    return FAISS.load_local(VECTOR_DIR, embeddings, allow_dangerous_deserialization=True)


@st.cache_resource(show_spinner=False)
def get_llm():
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)


@st.cache_resource(show_spinner=False)
def load_call_graph_cached():
    if os.path.exists(CALLGRAPH_PATH):
        try:
            with open(CALLGRAPH_PATH, "r", encoding="utf-8") as f:
                graph = json.load(f)
            return graph
        except Exception:
            return {}
    return {}


@st.cache_data(show_spinner=False)
def build_call_graph_html(call_graph, focus_symbol=None, max_depth=2):
    """
    Build an interactive call graph HTML using PyVis.
    Cached so switching focus is cheap and doesn't touch LLM/vectorstore.
    """
    try:
        net = Network(height="650px", width="100%", directed=True)
        G = nx.DiGraph()

        # Build graph structure
        for caller, callees in call_graph.items():
            for callee in callees:
                G.add_edge(caller, callee)

        # Subgraph if focus is selected
        if focus_symbol and focus_symbol in G.nodes:
            nodes_to_show = {focus_symbol}
            frontier = {focus_symbol}
            for _ in range(max_depth):
                new_frontier = set()
                for n in frontier:
                    neighbors = list(G.successors(n)) + list(G.predecessors(n))
                    new_frontier.update(neighbors)
                nodes_to_show.update(new_frontier)
                frontier = new_frontier
            H = G.subgraph(nodes_to_show)
        else:
            H = G

        # Add nodes+edges to PyVis
        for node in H.nodes():
            net.add_node(node, label=node, title=node, color="#6EC1E4")

        for u, v in H.edges():
            net.add_edge(u, v, color="#999999")

        net.set_options(
            """
        const options = {
          "nodes": {
            "shape": "dot",
            "size": 16,
            "font": {"size": 14}
          },
          "edges": {
            "color": {"inherit": true},
            "arrows": {"to": {"enabled": true}},
            "smooth": false
          },
          "physics": {
            "enabled": true,
            "stabilization": {"iterations": 150}
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """
        )

        html = net.generate_html("callgraph.html")
        return html
    except Exception as e:
        return f"<p>Error rendering call graph: {e}</p>"


def render_call_graph(call_graph, focus_symbol=None, max_depth=2):
    html_code = build_call_graph_html(call_graph, focus_symbol, max_depth)
    components.html(html_code, height=700, scrolling=True)


# Instantiate cached heavy objects once
embeddings = get_embeddings()
try:
    vectorstore = get_vectorstore()
    print("✅ FAISS vectorstore loaded (cached)")
except Exception:
    vectorstore = None
    print("⚠️ No FAISS index found yet. Ingest a repo first.")

llm = get_llm()


# ===============================
# 🧠 LLM PROMPT
# ===============================
prompt = ChatPromptTemplate.from_template(
    """
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
- **Where in the code:** Mention the most relevant files and line ranges using the format `path: start_line–end_line`.
- **Navigation Tips:** Which files/functions to open first and why.

If you are uncertain or the context is insufficient, clearly say so and suggest where the developer should manually inspect.
"""
)


# ======================================================
# 📥 REPO INGESTION
# ======================================================
st.subheader("📦 Ingest a New Repository")

repo_url = st.text_input("🔗 Enter GitHub Repository URL or Local Path")

if st.button("🚀 Start Ingestion"):
    if not repo_url.strip():
        st.warning("⚠️ Please enter a repository URL or folder path.")
    else:
        try:
            with st.status("⚙️ Ingestion Pipeline Running...", expanded=True) as status:
                status.write("📥 Step 1: Cloning or opening repository...")
                status.write("🧩 Step 2: Parsing with Tree-sitter / AST / Regex...")
                status.write("🧠 Step 3: Embedding & building FAISS index...")
                ingest_repo(repo_url.strip())
                status.update(
                    label="✅ Repository indexed successfully! (Vectorstore + Call Graph)",
                    state="complete",
                )
            st.success("🎉 Ingestion complete!")

            # Clear caches so new repo/index/graph are picked up
            get_vectorstore.clear()
            load_call_graph_cached.clear()
            build_call_graph_html.clear()

            # Reset previous QA results
            for key in ["last_answer", "last_docs", "last_query"]:
                st.session_state.pop(key, None)

            # Reload vectorstore in this run (optional)
            try:
                vectorstore = get_vectorstore()
                print("✅ FAISS reloaded after ingestion")
            except Exception as e:
                print(f"⚠️ Failed to reload FAISS after ingestion: {e}")

        except Exception as e:
            st.error(f"❌ Error during ingestion: {type(e).__name__}: {e}")
            st.text(traceback.format_exc())


# ======================================================
# 📡 CALL GRAPH VIEWER SECTION
# ======================================================
st.divider()
st.subheader("📡 Call Graph Explorer")

call_graph = load_call_graph_cached()

if not call_graph:
    st.info("ℹ️ No call graph available. Ingest a repository with Python functions first.")
else:
    all_nodes = sorted(call_graph.keys())
    focus_symbol = st.selectbox(
        "🔍 Focus on a specific function (optional):",
        options=["<Show full graph>"] + all_nodes,
        index=0,
        key="callgraph_focus",
    )

    if focus_symbol == "<Show full graph>":
        focus_symbol = None

    render_call_graph(call_graph, focus_symbol=focus_symbol, max_depth=2)


# ======================================================
# 📂 ENSURE VECTORSTORE EXISTS
# ======================================================
if vectorstore is None:
    st.warning("⚠️ No FAISS index found. Please ingest a repository first.")
    st.stop()


# ======================================================
# 🔁 QUERY REWRITING (for better retrieval)
# ======================================================
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


def rewrite_query_if_enabled(query: str, enabled: bool) -> str:
    if not enabled:
        return query
    try:
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


# ======================================================
# 🧠 METADATA FILTERING (Implicit)
# ======================================================
def infer_metadata_filters_from_query(query: str):
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


# ======================================================
# 5️⃣ RETRIEVAL – VECTOR + HYBRID RERANKING (NO LLM RERANK)
# ======================================================
def stage1_vector_search(query, k=16):
    """Retriever 1: plain vector search (no filters)."""
    docs_and_scores = vectorstore.similarity_search_with_score(query, k=k)
    print(
        f"🔎 Stage 1 – Vector search retrieved {len(docs_and_scores)} chunks for query: {query!r}"
    )
    return docs_and_scores  # list of (doc, score)


def hybrid_rerank(query, docs_and_scores, inferred_filters, top_k=6):
    """
    Hybrid reranking:
    - base vector similarity (FAISS distance → similarity)
    - metadata match (language, node_type, path)
    - symbol / parent_class matches
    - code heuristics (def/class/import/comments)
    - path weighting (views/models/controllers/utils)
    - embedding cosine similarity (HuggingFace)
    """
    if not docs_and_scores:
        return []

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


# ======================================================
# 🧹 DEDUPLICATION (exact + semantic)
# ======================================================
def deduplicate_docs(docs, semantic=True, threshold=0.9):
    """
    Remove duplicate chunks based on:
    - exact (path, start_line, end_line)
    - optional semantic similarity via embeddings for near-duplicates
    """
    if not docs:
        return docs

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
                    sim = float(
                        np.dot(v, prev_v)
                        / ((v_norm) * (np.linalg.norm(prev_v) + 1e-8))
                    )
                    if sim >= threshold:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    seen_vecs.append(v)
            except Exception:
                # If embeddings fail, fall back to exact-only
                pass

        if not is_duplicate:
            seen_keys.add(key)
            unique.append(d)

    if len(unique) < len(docs):
        print(f"🧹 Deduplicated {len(docs)} → {len(unique)} chunks")
    return unique


# ======================================================
# 🧩 CONTEXTUAL EXPANSION (NO DOC MUTATION)
# ======================================================
def get_expanded_context(docs, repo_path=DEFAULT_REPO_PATH, window=20):
    """
    Expand each doc with surrounding lines (siblings/context)
    without mutating the Document objects.
    """
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


# ======================================================
# 🧠 HEURISTIC CHUNK SUMMARY & TITLE
# ======================================================
def summarize_chunk_heuristic(doc):
    """
    Very lightweight heuristic summary:
    - Use first docstring or comment line if available
    - Otherwise use first non-empty line
    """
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


def chunk_title(doc):
    m = doc.metadata or {}
    path = (m.get("path") or "unknown").replace("\\", "/")
    symbol = m.get("symbol_name")
    node_type = m.get("node_type") or "chunk"
    if symbol:
        return f"{path} → {symbol}"
    return f"{path} → {node_type}"


# ======================================================
# 🧩 BUILD CONTEXT & SOURCES
# ======================================================
def build_context_and_sources(docs, expanded_map, max_chars_per_doc=1200):
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
        merged = merged[:max_chars_per_doc]  # safety trim

        context_parts.append(header + "\n" + merged)
        source_lines.append(f"{i}. {path}: {start}–{end}")

    context_str = "\n\n-----\n\n".join(context_parts)
    sources_str = "\n".join(source_lines) if source_lines else "None"
    return context_str, sources_str


# ======================================================
# 🔎 SMALL HELPERS FOR UI
# ======================================================
def matched_terms_in_chunk(query: str, doc):
    q_tokens = set(re.findall(r"[a-zA-Z_]\w*", query.lower()))
    text_tokens = set(re.findall(r"[a-zA-Z_]\w*", (doc.page_content or "").lower()))
    common = sorted(q_tokens.intersection(text_tokens))
    return common[:10]


def breadcrumb_for_path(path: str):
    parts = path.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return path
    return " › ".join(parts)


def load_file_segment(meta, repo_path=DEFAULT_REPO_PATH, padding=20):
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


# ======================================================
# 🔁 MULTI-HOP RETRIEVAL (no extra LLM calls)
# ======================================================
def build_followup_queries(original_query: str, seed_docs, max_queries: int = 3):
    """
    Build simple follow-up queries from the top docs using:
    - symbol_name
    - parent_class
    - file name / module
    - directory name
    - imports (if present in metadata)
    """
    followups = set()

    for d in seed_docs:
        m = d.metadata or {}
        path = (m.get("path") or "").replace("\\", "/")
        symbol = (m.get("symbol_name") or "").strip()
        parent = (m.get("parent_class") or "").strip()

        filename = os.path.basename(path)
        module, _ = os.path.splitext(filename)
        directory = os.path.dirname(path).split("/")[-1] if "/" in path else ""

        # From symbol
        if symbol:
            followups.add(f"{symbol} implementation in {filename}")
            followups.add(f"{symbol} usage {module}")

        # From parent class
        if parent:
            followups.add(f"{parent} class methods in {filename}")
            followups.add(f"{parent} initialization {module}")

        # From path tokens
        if module:
            followups.add(f"{module} logic {symbol or parent}")
        if directory:
            followups.add(f"{directory} {symbol or parent} flow")

        # From imports metadata if available
        imports = m.get("imports") or []
        if isinstance(imports, list):
            for imp in imports[:3]:  # limit for safety
                imp_name_match = re.findall(
                    r"from\s+([\w\.]+)\s+import|import\s+([\w\.]+)", imp
                )
                for g1, g2 in imp_name_match:
                    name = g1 or g2
                    if name:
                        followups.add(f"{name} related to {symbol or parent or module}")

    # Ensure queries are reasonably short and meaningful
    cleaned = []
    for q in followups:
        q_clean = " ".join(q.split())
        if len(q_clean) > 3 and len(q_clean.split()) <= 12:
            cleaned.append(q_clean)

    # De-duplicate and trim
    cleaned = list(dict.fromkeys(cleaned))
    trimmed = cleaned[:max_queries]
    print("🔁 Multi-hop follow-up queries:", trimmed)
    return trimmed


def multi_hop_retrieve(
    query: str, inferred_filters: dict, hops: int = 2, base_k: int = 16, top_k: int = 6
):
    """
    Two-hop retrieval:
    Hop 1: normal vector search + hybrid rerank.
    Hop 2: build follow-up queries from best docs, retrieve again, merge, rerank.
    No extra LLM calls; all heuristic.
    """
    # Hop 1
    hop1_scores = stage1_vector_search(query, k=base_k)
    hop1_docs = hybrid_rerank(query, hop1_scores, inferred_filters, top_k=top_k)

    if hops <= 1 or not hop1_docs:
        return hop1_docs

    # Build follow-up queries from hop1 docs
    followup_queries = build_followup_queries(query, hop1_docs, max_queries=3)
    if not followup_queries:
        print("🔁 Multi-hop: no follow-up queries generated; returning hop1 docs.")
        return hop1_docs

    # Hop 2 – collect docs+scores from follow-up queries
    all_scores = list(hop1_scores)
    for fq in followup_queries:
        hop2_scores = stage1_vector_search(fq, k=12)
        all_scores.extend(hop2_scores)

    # Hybrid rerank on combined candidates using original query
    combined_docs = hybrid_rerank(query, all_scores, inferred_filters, top_k=top_k)
    # Deduplicate exact docs (no semantic here, we do semantic later)
    combined_docs = deduplicate_docs(combined_docs, semantic=False)
    print(
        f"🔁 Multi-hop: combined {len(all_scores)} candidates → {len(combined_docs)} docs after rerank+dedup."
    )
    return combined_docs


# ======================================================
# 💬 QUERY INTERFACE (with caching of last result)
# ======================================================
st.divider()
st.subheader("💡 Ask Questions About Your Codebase")

enable_query_rewrite = st.checkbox(
    "✏️ Enable smart query rewriting (improves search)",
    value=True,
)

enable_multi_hop = st.checkbox(
    "🔁 Enable multi-hop retrieval (follow related files/symbols)",
    value=True,
)

query = st.text_input(
    "🔍 Your question (e.g., 'Where is judgment prediction implemented?'):",
    key="user_query",
)

run_query = st.button("🚀 Run Query", type="primary")


if run_query and query:
    with st.spinner("🔎 Running hybrid + multi-hop retrieval over your codebase..."):
        try:
            # 0️⃣ Optionally rewrite query for better retrieval
            effective_query = rewrite_query_if_enabled(query, enable_query_rewrite)

            # 1️⃣ Infer metadata filters (from original human query)
            inferred_filters = infer_metadata_filters_from_query(query)

            # 2️⃣ Retrieval (single-hop or multi-hop)
            if enable_multi_hop:
                candidate_docs = multi_hop_retrieve(
                    effective_query,
                    inferred_filters,
                    hops=2,
                    base_k=16,
                    top_k=6,
                )
            else:
                # Original single-hop behavior
                stage1_docs_and_scores = stage1_vector_search(effective_query, k=16)
                candidate_docs = hybrid_rerank(
                    effective_query,
                    stage1_docs_and_scores,
                    inferred_filters,
                    top_k=6,
                )

            # 3️⃣ Deduplicate (exact + semantic)
            candidate_docs = deduplicate_docs(
                candidate_docs, semantic=True, threshold=0.9
            )

            # Limit final matches to 2 for answer + UI
            final_docs = candidate_docs[:2]

            if not final_docs:
                st.warning("⚠️ No relevant chunks retrieved from the codebase.")
            else:
                # 4️⃣ Contextual expansion
                expanded_map = get_expanded_context(
                    final_docs, repo_path=DEFAULT_REPO_PATH
                )

                # 5️⃣ Build final context + sources
                context_str, sources_str = build_context_and_sources(
                    final_docs, expanded_map
                )

                # 6️⃣ Construct prompt and call LLM
                messages = prompt.format_messages(
                    context=context_str,
                    sources=sources_str,
                    input=query,
                )
                response = llm.invoke(messages)
                answer = response.content

                # Store in session_state so changing call graph doesn't recompute
                st.session_state["last_answer"] = answer
                st.session_state["last_docs"] = final_docs
                st.session_state["last_query"] = query

        except Exception as e:
            st.error(f"❌ Error while answering: {type(e).__name__}: {e}")
            st.text(traceback.format_exc())

# ======================================================
# 📤 SHOW LAST RESULT (PERSIST ACROSS UI CHANGES)
# ======================================================
if "last_answer" in st.session_state and "last_docs" in st.session_state:
    answer = st.session_state["last_answer"]
    final_docs = st.session_state["last_docs"]
    last_query = st.session_state.get("last_query", "")

    st.subheader("🤖 AI Answer")
    st.markdown(answer)

    # Show top matches (code snippets + UX improvements)
    st.subheader("📂 Top Code Matches")
    for i, d in enumerate(final_docs, start=1):
        m = d.metadata or {}
        path_raw = m.get("path") or "unknown"
        path = path_raw.replace("\\", "/")
        breadcrumb = breadcrumb_for_path(path)
        summary = summarize_chunk_heuristic(d)
        title = chunk_title(d)
        matched_terms = matched_terms_in_chunk(last_query, d)

        st.markdown(f"### 🧩 Match {i}")
        st.markdown(f"- **Title:** `{title}`")
        st.markdown(f"- **Location:** `{breadcrumb}`")
        st.markdown(f"- **Lines:** {m.get('start_line')}–{m.get('end_line')}")
        st.markdown(f"- **Symbol:** `{m.get('symbol_name')}`")
        st.markdown(f"- **Parser:** `{m.get('parser_used')}`")
        st.markdown(f"- **Heuristic Summary:** {summary}")
        if matched_terms:
            st.markdown(f"- **Matched Terms:** `{', '.join(matched_terms)}`")

        st.code(d.page_content, language=m.get("language") or "python")

        # Jump-to-code / surrounding viewer
        with st.expander("👁 View surrounding code"):
            seg = load_file_segment(m, repo_path=DEFAULT_REPO_PATH, padding=20)
            if seg is not None:
                segment_text, seg_start, seg_end = seg
                st.markdown(f"_Showing lines {seg_start}–{seg_end} from `{path}`_")
                st.code(segment_text, language=m.get("language") or "python")
            else:
                st.info("Unable to load surrounding file segment.")
