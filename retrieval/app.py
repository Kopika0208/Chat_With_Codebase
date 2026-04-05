# app.py
"""
Main Streamlit application for Chat with Codebase.
Handles UI, LLM integration, and orchestrates retrieval modules.
"""
import sys, os
# Force add project root (parent of retrieval/) to PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from redis_storage import list_repos as list_redis_repos

print("DEBUG: USING PROJECT ROOT =", PROJECT_ROOT)
print("DEBUG: CURRENT WORKING DIRECTORY =", os.getcwd())

# ===============================
# 📂 MULTI-REPO SUPPORT
# ===============================
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

def list_ingested_repos():
    """List all ingested repositories from Redis."""
    return list_redis_repos()


def _get_repo_source_path(repo_name: str) -> str:
    """Resolve the best available path to source files for a repo.
    
    Tries in order:
    1. repos/<repo_name>/ (git clone)
    2. data/<repo_name>/api_source/ (API ingestion snapshot)
    3. data/<repo_name>/ (fallback)
    """
    git_path = os.path.join(PROJECT_ROOT, "repos", repo_name)
    if os.path.isdir(git_path):
        return git_path
    
    api_source = os.path.join(DATA_DIR, repo_name, "api_source")
    if os.path.isdir(api_source):
        return api_source
    
    return os.path.join(DATA_DIR, repo_name)

import traceback
import streamlit as st
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client

from ingestion.ingest import ingest_repo, VECTOR_DIR, CALLGRAPH_PATH
from cache import (
    get_vectorstore,
    get_llm,
    load_call_graph_cached,
    load_boot_chain_cached,
    load_core_structures_cached,
    get_graph_rag_retriever,
    load_knowledge_graph_cached,
    load_graph_traversal_cached,
    load_symbol_table_cached,
    load_dataflow_data_cached,
    load_async_patterns_cached,
    get_unified_retriever,
    get_query_understanding,
)
from retrieval import (
    infer_metadata_filters_from_query,
    multi_hop_retrieve,
    deduplicate_docs,
    get_expanded_context,
    build_context_and_sources,
    matched_terms_in_chunk,
    stage1_vector_search,
    hybrid_rerank,
    symbol_aware_retrieve,
)
from utils import (
    rewrite_query_if_enabled,
    summarize_chunk_heuristic,
    chunk_title,
    breadcrumb_for_path,
    load_file_segment,
)
from graph import render_call_graph
from reasoning import get_reasoning_chain
from onboarding import (
    CodebaseAnalyzer,
    render_project_overview,
    render_entry_exit_points,
    render_roadmap,
    render_file_tree,
    render_navigation_hints,
    render_weak_documentation_section,
    render_summary,
)
from code_health.visualization import render_code_health_tab
from contributions_viz import render_contributions_tab
from contributions_analyzer import load_contributions_analyzer, ContributionsDataAnalyzer

# ===============================
# Evaluation metrics collection
# ===============================
try:
    from evaluation.collector import save_retrieval_metrics
except ImportError:
    save_retrieval_metrics = None

# ===============================
# ⚙️ SETUP
# ===============================
load_dotenv()
st.set_page_config(page_title="Chat with Your Codebase", layout="wide")
st.title("💬 Chat with Your Codebase – Multi-Repo + Multi-Hop + Call Graph")

LANGCHAIN_PROJECT = "chat-with-codebase"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_TRACING"] = "false"
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT

# Temporarily disable LangSmith tracing/requests to avoid monthly rate limit usage.
os.environ.pop("LANGCHAIN_API_KEY", None)
os.environ.pop("LANGCHAIN_LLM_ENDPOINT", None)
os.environ.pop("LANGCHAIN_LIVE_CHAT_API_KEY", None)

client = None
print("⚠️ LangSmith tracing is disabled to prevent API quota exhaustion.")

# Initialize session state for multi-repo support
if "active_repo" not in st.session_state:
    st.session_state["active_repo"] = None

if "last_active_repo" not in st.session_state:
    st.session_state["last_active_repo"] = None


# ===============================
# 🧠 LLM PROMPT TEMPLATES
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

# Prompt for contribution/git history queries
contribution_prompt = ChatPromptTemplate.from_template(
    """
You are an expert assistant analyzing code contributions and git history.

Based on the contribution data provided, answer the following question about project development, commits, authors, and contribution patterns.

<contribution_context>
{contribution_context}
</contribution_context>

Question: {input}

Provide a comprehensive answer including:
- **Direct Answer:** Clearly address the question asked.
- **Key Metrics:** Share relevant statistics (commits, authors, files changed, lines added/deleted).
- **Insights:** Provide analysis about development patterns, activity trends, or contributor involvement.
- **Timeline:** If relevant, mention when changes occurred.
- **Related Information:** Provide any additional context that helps understand the project's development history.

Be precise, data-driven, and help the developer understand the project's development progress and team contributions.
"""
)

startup_prompt = ChatPromptTemplate.from_template(
    """
You are an expert assistant helping a developer understand application startup behavior.

The user is asking about entry points, startup flow, boot sequence, or how the application reaches a ready state.

Here is the boot sequence graph, explain the startup lifecycle in order.

<boot_chain>
{boot_chain}
</boot_chain>

Question: {input}

Respond with:

- **Entry Point:** The most likely startup function(s) and file locations.
- **Startup Lifecycle:** Ordered explanation from boot to ready.
- **Ready State:** What likely indicates the application is ready, or say if it is heuristic.
- **Where to Inspect:** The most relevant files/functions to open first.

If the boot-chain data is incomplete or heuristic, say that clearly instead of overstating certainty.
"""
)

dataflow_prompt = ChatPromptTemplate.from_template(
    """
You are an expert assistant helping a developer understand how data moves through a codebase.

Here is a traced request/dataflow path from the application graph. Explain the flow in order from entry to downstream handling.

<dataflow_trace>
{dataflow_trace}
</dataflow_trace>

Question: {input}

Respond with:

- **Entry Layer:** Where the request or input first enters.
- **Flow Order:** Explain each hop in order.
- **Data Transformation:** Mention parameter passing, return propagation, and hand-offs when present.
- **Downstream Layer:** Identify the most likely business-logic and data-access boundary reached.
- **Where to Inspect:** List the most relevant files/functions to open first.

If the trace is heuristic or incomplete, say that clearly.
"""
)

business_logic_prompt = ChatPromptTemplate.from_template(
    """
You are an expert assistant helping a developer identify where the core business logic and heavy lifting of a codebase live.

Here are the highest-importance knowledge-graph nodes ranked by structural centrality.

<important_nodes>
{important_nodes}
</important_nodes>

Question: {input}

Respond with:

- **Core Logic Summary:** What parts of the code appear to do the main work.
- **Top Candidates:** The most important functions/classes and why they matter.
- **Architecture Role:** How these nodes likely fit together.
- **Where to Inspect:** Which files/functions to open first.

Be explicit when the ranking is heuristic.
"""
)

data_structures_prompt = ChatPromptTemplate.from_template(
    """
You are an expert assistant helping a developer identify the core data structures and state owners in a codebase.

Here is a ranked summary of likely state-owning classes and the symbols they contain.

<core_structures>
{core_structures}
</core_structures>

Question: {input}

Respond with:

- **State Owners:** Which classes or structures appear to hold state.
- **How Data Is Stored:** The likely organization of core data.
- **Important Fields/Children:** The most relevant contained symbols.
- **Where to Inspect:** Which classes/files to open first.

Be clear if the result is inferred from symbol containment rather than full runtime semantics.
"""
)

async_prompt = ChatPromptTemplate.from_template(
    """
You are an expert assistant helping a developer understand asynchronous and background execution patterns in a codebase.

Here is the extracted async/background execution summary.

<async_patterns>
{async_patterns}
</async_patterns>

Question: {input}

Respond with:

- **Async Model:** What async/concurrency mechanisms the codebase appears to use.
- **Key Patterns:** Important async functions, background jobs, or thread/task dispatch points.
- **Execution Flow:** How background work is likely triggered and executed.
- **Where to Inspect:** The most relevant files/functions to open first.

If there are no strong async signals, say so plainly.
"""
)

# ===============================
# 📂 REPOSITORY SELECTION & MANAGEMENT
# ===============================
st.divider()
st.subheader("📂 Repository Management")

col1, col2 = st.columns([2, 1])

with col1:
    repos = list_ingested_repos()
    
    if not repos:
        st.warning("ℹ️ No repositories ingested yet. Please ingest one below.")
        active_repo = None
    else:
        active_repo = st.selectbox(
            "Select a repository to work with:",
            repos,
            index=0,
            key="active_repo_selector"
        )
        
        if active_repo and st.session_state.get("last_active_repo") != active_repo:
            st.session_state["last_active_repo"] = active_repo
            # Clear repo-specific caches when switching repos
            get_vectorstore.clear()
            load_call_graph_cached.clear()
            load_boot_chain_cached.clear()
            load_core_structures_cached.clear()
            get_graph_rag_retriever.clear()
            load_knowledge_graph_cached.clear()
            load_graph_traversal_cached.clear()
            load_symbol_table_cached.clear()
            load_dataflow_data_cached.clear()
            load_async_patterns_cached.clear()
            get_unified_retriever.clear()
            # Clear previous QA results
            for key in ["last_answer", "last_docs", "last_query"]:
                st.session_state.pop(key, None)
            st.rerun()
        
        st.session_state["active_repo"] = active_repo

with col2:
    st.markdown("**Ingested Repos:**")
    st.markdown(f"**{len(repos)}** repo(s)")

# ===============================
# 📥 REPO INGESTION SECTION
# ===============================
st.divider()
st.subheader("📦 Ingest a New Repository")

ingest_col1, ingest_col2 = st.columns([3, 1])

with ingest_col1:
    repo_url = st.text_input("🔗 Enter GitHub Repository URL or Local Path")

with ingest_col2:
    st.write("")  # Spacing
    ingest_button = st.button("🚀 Ingest", type="primary")

if ingest_button:
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

            # Clear ALL repo-dependent caches
            get_vectorstore.clear()
            load_call_graph_cached.clear()
            load_boot_chain_cached.clear()
            load_core_structures_cached.clear()
            get_graph_rag_retriever.clear()
            load_knowledge_graph_cached.clear()
            load_graph_traversal_cached.clear()
            load_symbol_table_cached.clear()
            load_dataflow_data_cached.clear()
            load_async_patterns_cached.clear()
            get_unified_retriever.clear()

            # Reset previous QA results
            for key in ["last_answer", "last_docs", "last_query"]:
                st.session_state.pop(key, None)

            # Rerun to update repo list and auto-select new repo
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error during ingestion: {type(e).__name__}: {e}")
            st.text(traceback.format_exc())


# ======================================================
# ✅ ENSURE REPO IS SELECTED AND VECTORSTORE EXISTS
# ======================================================
if not active_repo:
    st.info("ℹ️ Please select or ingest a repository to continue.")
    st.stop()

try:
    vectorstore = get_vectorstore(active_repo)
    print("✅ FAISS vectorstore loaded (cached)")
except Exception as e:
    vectorstore = None
    print(f"⚠️ No FAISS index found for {active_repo}: {e}")
    st.warning(f"⚠️ No FAISS index found. Please ensure the repository was ingested correctly.")
    st.stop()

llm = get_llm()


# ======================================================
# 📡 CALL GRAPH VIEWER SECTION
# ======================================================
st.divider()
st.subheader("📡 Call Graph Explorer")

call_graph = load_call_graph_cached(active_repo)

if not call_graph:
    st.info("ℹ️ No call graph available for this repository. Ingest a repository with Python functions first.")
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
# 📚 ONBOARDING & DOCUMENTATION TAB
# ======================================================
st.divider()
st.subheader("📚 Onboarding & Documentation")

# Initialize analyzer
try:
    symbol_table = load_symbol_table_cached(active_repo)
    knowledge_graph = load_knowledge_graph_cached(active_repo)
    dataflow_data = load_dataflow_data_cached(active_repo)
    
    analyzer = CodebaseAnalyzer(
        call_graph=call_graph,
        symbol_table=symbol_table,
        repo_path=os.path.join("data", active_repo),
        root_dir=os.path.join("repos", active_repo) if os.path.exists(os.path.join("repos", active_repo)) else "",
        vectorstore=vectorstore,  # For file discovery and metadata extraction
        knowledge_graph=knowledge_graph,  # Semantic relationships between symbols
        dataflow_data=dataflow_data  # Data flow dependencies
    )
    
    # Create tabs for onboarding features
    onboarding_tabs = st.tabs([
        "📊 Overview",
        "🚀 Entry/Exit Points",
        "🗺️ Roadmap",
        "🌳 File Structure",
        "🧭 Navigation",
        "📝 Documentation",
        "💪 Code Health",
        "👥 Contributions",
    ])
    
    with onboarding_tabs[0]:  # Overview Tab
        st.markdown("### Project Summary & Statistics")
        stats = analyzer.get_project_stats()
        
        # Try to generate enhanced summary
        try:
            summary = analyzer.generate_project_summary(llm=llm)
            render_summary(summary)
        except Exception as e:
            print(f"⚠️ Summary generation failed: {e}")
        
        st.divider()
        render_project_overview(stats)
    
    with onboarding_tabs[1]:  # Entry/Exit Points Tab
        entry_points = analyzer.get_entry_points()
        exit_points = analyzer.get_exit_points()
        render_entry_exit_points(entry_points, exit_points)
    
    with onboarding_tabs[2]:  # Roadmap Tab
        roadmap = analyzer.get_dependency_order()
        render_roadmap(roadmap)
    
    with onboarding_tabs[3]:  # File Structure Tab
        file_tree = analyzer.get_file_tree()
        render_file_tree(file_tree)
    
    with onboarding_tabs[4]:  # Navigation Tab
        st.markdown("### Navigate Code Relationships")
        
        # Get all unique symbols for selection
        all_symbols = sorted(analyzer.symbol_table.keys())
        
        if all_symbols:
            selected_symbol = st.selectbox(
                "Select a symbol to explore:",
                all_symbols,
                key="navigation_symbol_selector"
            )
            
            if selected_symbol:
                render_navigation_hints(analyzer, selected_symbol)
        else:
            st.info("No symbols found in this repository.")
    
    with onboarding_tabs[5]:  # Documentation Tab
        weak_docs = analyzer.get_files_with_weak_docs()
        render_weak_documentation_section(weak_docs, llm, analyzer)
    
    with onboarding_tabs[6]:  # Code Health & Quality Tab
        try:
            # Get the actual repo path from repos or data directory
            repo_source_path = os.path.join("repos", active_repo) if os.path.exists(os.path.join("repos", active_repo)) else os.path.join("data", active_repo)
            render_code_health_tab(repo_source_path, call_graph, symbol_table)
        except Exception as e:
            st.error(f"[ERROR] Error loading Code Health analysis: {type(e).__name__}: {e}")
            print(f"Debug - repo_source_path: {repo_source_path}")
            print(traceback.format_exc())

    with onboarding_tabs[7]:  # Contributions Tab
        st.markdown("### 👥 Code Contributions & Commit History")
        try:
            render_contributions_tab(active_repo)
        except Exception as e:
            st.error(f"[ERROR] Error loading Contributions analysis: {type(e).__name__}: {e}")
            print(traceback.format_exc())

except Exception as e:
    st.error(f"❌ Error initializing onboarding module: {type(e).__name__}: {e}")
    print(traceback.format_exc())


# ======================================================
# 🔌 QUERY PROCESSING PIPELINE
# ======================================================
def _format_boot_chain_for_prompt(boot_chain: dict) -> str:
    """Format boot-chain metadata into a compact startup summary for the LLM."""
    if not boot_chain:
        return "No boot-chain metadata is available for this repository."

    entry_points = boot_chain.get("entry_points", [])
    ordered_steps = boot_chain.get("ordered_steps", [])
    ready_candidates = boot_chain.get("ready_candidates", [])

    lines = [boot_chain.get("summary", "")]

    if entry_points:
        lines.append("Entry points:")
        for entry in entry_points[:5]:
            lines.append(
                f"- {entry.get('name')} in {entry.get('file')}:{entry.get('line', '?')}"
            )

    if ordered_steps:
        lines.append("Ordered boot steps:")
        for step in ordered_steps[:20]:
            parent = step.get("called_by") or "ROOT"
            lines.append(
                f"- depth={step.get('depth', '?')} {parent} -> {step.get('name')} "
                f"({step.get('file')}:{step.get('line', '?')}) callees={step.get('callee_count', 0)}"
            )

    if ready_candidates:
        lines.append("Ready-state candidates:")
        for candidate in ready_candidates[:10]:
            lines.append(
                f"- {candidate.get('name')} ({candidate.get('file')}:{candidate.get('line', '?')})"
            )

    return "\n".join(line for line in lines if line)


def _run_startup_query(query: str, repo_name: str) -> dict:
    """Answer startup questions from precomputed boot-chain metadata."""
    boot_chain = load_boot_chain_cached(repo_name)
    if not boot_chain:
        st.warning("⚠️ No boot-chain metadata found. Re-ingest the repository to enable startup lifecycle answers.")
        return None

    llm = get_llm()
    boot_chain_context = _format_boot_chain_for_prompt(boot_chain)
    response = llm.invoke(
        startup_prompt.format_prompt(
            boot_chain=boot_chain_context,
            input=query,
        ).to_messages()
    )

    from langchain_core.documents import Document

    boot_doc = Document(
        page_content=boot_chain_context,
        metadata={
            "path": "boot_chain.json",
            "symbol_name": "startup_lifecycle",
            "start_line": 0,
            "end_line": 0,
            "parser_used": "boot_chain_precompute",
            "language": "json",
        }
    )

    return {
        "answer": response.content.strip(),
        "final_docs": [boot_doc],
        "context": boot_chain_context,
        "sources": "boot_chain.json",
        "boot_chain_used": True,
    }


def _rank_knowledge_graph_nodes(knowledge_graph: dict, top_k: int = 15) -> list:
    """Rank KG nodes by a lightweight centrality-style score."""
    raw_nodes = knowledge_graph.get("nodes", []) if isinstance(knowledge_graph, dict) else []
    raw_edges = knowledge_graph.get("edges", []) if isinstance(knowledge_graph, dict) else []

    nodes = {}
    for node in raw_nodes:
        if isinstance(node, dict):
            node_id = node.get("id") or node.get("node_id")
            if node_id:
                nodes[node_id] = node

    inbound = {node_id: 0 for node_id in nodes}
    outbound = {node_id: 0 for node_id in nodes}
    edge_types = {node_id: set() for node_id in nodes}

    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type", "unknown")
        if source in outbound:
            outbound[source] += 1
            edge_types[source].add(edge_type)
        if target in inbound:
            inbound[target] += 1
            edge_types[target].add(edge_type)

    ranked = []
    for node_id, node in nodes.items():
        score = outbound[node_id] * 1.2 + inbound[node_id] + len(edge_types[node_id]) * 1.5
        ranked.append({
            "id": node_id,
            "name": node.get("name", node_id),
            "type": node.get("type", "unknown"),
            "file": node.get("file", ""),
            "line": node.get("line", 0),
            "importance_score": round(score, 3),
            "out_degree": outbound[node_id],
            "in_degree": inbound[node_id],
            "edge_types": sorted(edge_types[node_id]),
        })

    ranked.sort(key=lambda item: (-item["importance_score"], -item["out_degree"], -item["in_degree"], item["name"]))
    return ranked[:top_k]


def _format_important_nodes(nodes: list) -> str:
    if not nodes:
        return "No ranked knowledge-graph nodes were available."
    return "\n".join(
        f"- {node['name']} [{node['type']}] at {node['file']}:{node['line']} "
        f"| score={node['importance_score']} | out={node['out_degree']} in={node['in_degree']} "
        f"| edges={', '.join(node['edge_types']) or 'none'}"
        for node in nodes
    )


def _run_business_logic_query(query: str, repo_name: str, query_info: dict) -> dict:
    """Answer business-logic questions from ranked KG nodes."""
    knowledge_graph = load_knowledge_graph_cached(repo_name)
    ranked_nodes = _rank_knowledge_graph_nodes(knowledge_graph, top_k=15)
    context = _format_important_nodes(ranked_nodes)
    llm = get_llm()
    response = llm.invoke(
        business_logic_prompt.format_prompt(
            important_nodes=context,
            input=query,
        ).to_messages()
    )

    from langchain_core.documents import Document
    docs = [
        Document(
            page_content=context,
            metadata={
                "path": "knowledge_graph.json",
                "symbol_name": "important_business_logic_nodes",
                "start_line": 0,
                "end_line": 0,
                "parser_used": "kg_centrality_ranking",
                "language": "json",
            },
        )
    ]
    return {
        "answer": response.content.strip(),
        "final_docs": docs,
        "context": context,
        "sources": "knowledge_graph.json",
        "query_understanding": query_info,
    }


def _format_core_structures(core_structures: dict) -> str:
    structures = core_structures.get("structures", []) if isinstance(core_structures, dict) else []
    if not structures:
        return core_structures.get("summary", "No core structure summary is available.") if isinstance(core_structures, dict) else "No core structure summary is available."

    lines = [core_structures.get("summary", "")]
    for structure in structures[:15]:
        child_names = ", ".join(child.get("name", "") for child in structure.get("children", [])[:8])
        lines.append(
            f"- {structure.get('name')} at {structure.get('file')}:{structure.get('line', '?')} "
            f"| contained_symbols={structure.get('contained_symbol_count', 0)}"
            + (f" | children={child_names}" if child_names else "")
        )
    return "\n".join(line for line in lines if line)


def _run_data_structures_query(query: str, repo_name: str, query_info: dict) -> dict:
    """Answer data-structure/state questions from precomputed core structures."""
    core_structures = load_core_structures_cached(repo_name)
    context = _format_core_structures(core_structures)
    llm = get_llm()
    response = llm.invoke(
        data_structures_prompt.format_prompt(
            core_structures=context,
            input=query,
        ).to_messages()
    )

    from langchain_core.documents import Document
    docs = [
        Document(
            page_content=context,
            metadata={
                "path": "core_structures.json",
                "symbol_name": "core_data_structures",
                "start_line": 0,
                "end_line": 0,
                "parser_used": "core_structure_precompute",
                "language": "json",
            },
        )
    ]
    return {
        "answer": response.content.strip(),
        "final_docs": docs,
        "context": context,
        "sources": "core_structures.json",
        "query_understanding": query_info,
    }


def _format_async_patterns(async_patterns: dict) -> str:
    if not async_patterns:
        return "No async/background execution patterns were extracted."

    lines = []
    for file_path, entry in list(async_patterns.items())[:20]:
        if not isinstance(entry, dict):
            continue
        lines.append(f"- {file_path}: {entry.get('pattern_count', 0)} pattern(s)")
        for pattern in entry.get("patterns", [])[:8]:
            lines.append(
                f"  - {pattern.get('pattern_type')} {pattern.get('name')} at line {pattern.get('line', '?')}"
            )
    return "\n".join(lines) if lines else "No async/background execution patterns were extracted."


def _run_async_query(query: str, repo_name: str, query_info: dict) -> dict:
    """Answer async/concurrency questions from extracted async patterns."""
    async_patterns = load_async_patterns_cached(repo_name)
    context = _format_async_patterns(async_patterns)
    llm = get_llm()
    response = llm.invoke(
        async_prompt.format_prompt(
            async_patterns=context,
            input=query,
        ).to_messages()
    )

    from langchain_core.documents import Document
    docs = [
        Document(
            page_content=context,
            metadata={
                "path": "async_patterns.json",
                "symbol_name": "async_execution_patterns",
                "start_line": 0,
                "end_line": 0,
                "parser_used": "async_pattern_extractor",
                "language": "json",
            },
        )
    ]
    return {
        "answer": response.content.strip(),
        "final_docs": docs,
        "context": context,
        "sources": "async_patterns.json",
        "query_understanding": query_info,
    }


def _is_dataflow_query(query_info: dict, query: str) -> bool:
    """Detect questions asking for request/data flow across application layers."""
    if not query_info:
        return False

    query_lower = query.lower()
    flow_terms = ("data flow", "request flow", "through the layers", "through the application", "request through", "user request")
    return (
        query_info.get("intent") == "understand_flow"
        and any(term in query_lower for term in flow_terms)
    )


def _route_special_intent(query: str, repo_name: str, query_info: dict):
    """Dispatch non-general questions to curated data sources."""
    intent = (query_info or {}).get("intent")
    if intent == "understand_business_logic":
        return _run_business_logic_query(query, repo_name, query_info)
    if intent == "understand_data_structures":
        return _run_data_structures_query(query, repo_name, query_info)
    if intent == "understand_async":
        return _run_async_query(query, repo_name, query_info)
    if _is_dataflow_query(query_info, query):
        return _run_dataflow_query(query, repo_name, query_info)
    if query_info.get("is_startup_query"):
        startup_result = _run_startup_query(query, repo_name)
        if startup_result:
            startup_result["query_understanding"] = query_info
        return startup_result
    return None


def _format_dataflow_trace(trace_result: dict) -> str:
    """Convert a traced request path into prompt-friendly text."""
    if not trace_result or not trace_result.get("path"):
        return trace_result.get("summary", "No request/dataflow path could be traced.")

    lines = [trace_result.get("summary", "")]
    for step in trace_result.get("path", []):
        edge_type = step.get("incoming_edge_type") or "entry"
        edge_props = step.get("incoming_edge_properties") or {}
        line = (
            f"- {step.get('name')} [{step.get('type')}] "
            f"at {step.get('file')}:{step.get('line', '?')} via {edge_type}"
        )
        if edge_props.get("parameter_bindings"):
            bindings = ", ".join(
                f"{binding.get('argument_expr')} -> {binding.get('parameter')}"
                for binding in edge_props["parameter_bindings"][:5]
            )
            line += f" | params: {bindings}"
        if edge_props.get("assigned_to"):
            line += f" | assigned_to: {edge_props.get('assigned_to')}"
        lines.append(line)

    return "\n".join(lines)


def _discover_dataflow_entry_candidates(repo_name: str) -> list:
    """Discover likely request-entry symbols from existing repo metadata."""
    call_graph = load_call_graph_cached(repo_name) or {}
    symbol_table = load_symbol_table_cached(repo_name) or {}
    knowledge_graph = load_knowledge_graph_cached(repo_name) or {}
    dataflow_data = load_dataflow_data_cached(repo_name) or {}

    analyzer = CodebaseAnalyzer(
        call_graph=call_graph,
        symbol_table=symbol_table,
        repo_path=os.path.join("data", repo_name),
        root_dir=os.path.join("repos", repo_name) if os.path.exists(os.path.join("repos", repo_name)) else "",
        vectorstore=None,
        knowledge_graph=knowledge_graph,
        dataflow_data=dataflow_data,
    )

    candidates = []
    for entry in analyzer.get_entry_points():
        name = entry.get("name")
        if name:
            candidates.append(name)

    if not candidates:
        candidates = list(call_graph.keys())[:5]

    return candidates[:8]


def _run_dataflow_query(query: str, repo_name: str, query_info: dict) -> dict:
    """Answer cross-layer dataflow questions using a traced request path."""
    retriever = get_graph_rag_retriever(repo_name)
    if not retriever:
        st.warning("⚠️ Graph-RAG retriever is unavailable for dataflow tracing.")
        return None

    symbols = query_info.get("primary_symbols", [])
    entry_symbol = symbols[0].name if symbols else None
    target_symbol = symbols[1].name if len(symbols) > 1 else None

    trace_attempts = []
    if entry_symbol:
        trace_attempts.append(retriever.trace_request_path(entry_symbol, target_symbol))

    for candidate in _discover_dataflow_entry_candidates(repo_name):
        trace_attempts.append(retriever.trace_request_path(candidate, target_symbol))

    trace_result = max(
        trace_attempts,
        key=lambda item: (len(item.get("path", [])), len(item.get("documents", []))),
        default={},
    )

    if not trace_result.get("path"):
        candidate_text = ", ".join(_discover_dataflow_entry_candidates(repo_name)[:5]) or "none"
        trace_result = {
            "path": [],
            "documents": [],
            "summary": (
                "No concrete request/dataflow path could be traced from the current graph. "
                f"Candidate entry points discovered: {candidate_text}."
            ),
        }

    trace_context = _format_dataflow_trace(trace_result)
    if not trace_result.get("path"):
        from langchain_core.documents import Document
        return {
            "answer": (
                "I couldn't trace a concrete request-to-downstream dataflow path from the current graph data. "
                + trace_result.get("summary", "")
                + " Re-ingest the repo after the new cross-file dataflow changes, then retry this question."
            ),
            "final_docs": [
                Document(
                    page_content=trace_context,
                    metadata={
                        "path": "knowledge_graph.json",
                        "symbol_name": "request_dataflow_trace",
                        "start_line": 0,
                        "end_line": 0,
                        "parser_used": "graph_trace",
                        "language": "json",
                    },
                )
            ],
            "context": trace_context,
            "sources": "knowledge_graph.json + dataflow_analysis.json",
            "dataflow_trace_used": True,
            "query_understanding": query_info,
        }

    llm = get_llm()
    response = llm.invoke(
        dataflow_prompt.format_prompt(
            dataflow_trace=trace_context,
            input=query,
        ).to_messages()
    )

    final_docs = trace_result.get("documents", [])
    if not final_docs:
        from langchain_core.documents import Document
        final_docs = [
            Document(
                page_content=trace_context,
                metadata={
                    "path": "knowledge_graph.json",
                    "symbol_name": "request_dataflow_trace",
                    "start_line": 0,
                    "end_line": 0,
                    "parser_used": "graph_trace",
                    "language": "json",
                },
            )
        ]

    return {
        "answer": response.content.strip(),
        "final_docs": final_docs,
        "context": trace_context,
        "sources": "knowledge_graph.json + dataflow_analysis.json",
        "dataflow_trace_used": True,
        "query_understanding": query_info,
    }


def run_query_pipeline(query: str, repo_name: str, enable_query_rewrite: bool, enable_multi_hop: bool,
                      enable_reasoning_chain: bool, k: int = 10) -> dict:
    """Execute the complete query pipeline."""
    query_understanding = get_query_understanding(repo_name)
    query_info = query_understanding.understand(query)
    special_result = _route_special_intent(query, repo_name, query_info)
    if special_result:
        return special_result
    
    # Check if reasoning chain should be used
    if enable_reasoning_chain:
        try:
            reasoning_chain = get_reasoning_chain(active_repo)
            if reasoning_chain:
                result = reasoning_chain.reason(query, enable_graph_walk=True)
                return {
                    "answer": result["answer"],
                    "final_docs": result["enhanced_docs"],
                    "intent_info": result["intent"],
                    "symbols_info": result["symbols"],
                    "reasoning_trace": result["reasoning_trace"],
                }
            else:
                st.warning("⚠️ Reasoning chain unavailable, using standard retrieval")
        except Exception as e:
            st.error(f"❌ Error in reasoning chain: {type(e).__name__}: {e}")
            st.text(traceback.format_exc())
            return None
    
    # Standard retrieval pipeline
    try:
        # 0️⃣ Optionally rewrite query
        effective_query = rewrite_query_if_enabled(query, enable_query_rewrite)

        # 1️⃣ Infer metadata filters
        inferred_filters = infer_metadata_filters_from_query(query)

        # 2️⃣ Retrieval (single-hop, multi-hop, or symbol-driven)
        if enable_multi_hop:
            # Use symbol-driven ranking for better results
            try:
                candidate_docs = symbol_aware_retrieve(effective_query, repo_name=repo_name, top_k=8)

            except Exception as e:
                print(f"⚠️ Symbol-aware retrieval failed: {e}, falling back to multi-hop")
                candidate_docs = multi_hop_retrieve(
                    effective_query, inferred_filters, repo_name=repo_name, hops=2, base_k=16, top_k=8
                )
        else:
            scores = stage1_vector_search(effective_query, repo_name=repo_name, k=16)
            candidate_docs = hybrid_rerank(effective_query, scores, inferred_filters, top_k=8)

        # 3️⃣ Deduplicate
        candidate_docs = deduplicate_docs(
            candidate_docs, semantic=True, threshold=0.9
        )

        # 4️⃣ Limit results
        final_docs = candidate_docs[:2]

        if not final_docs:
            st.warning("⚠️ No relevant code found. Try rephrasing your question.")
            return None

        # 5️⃣ Build context and answer
        expanded_map = get_expanded_context(
            final_docs,
            repo_path=_get_repo_source_path(repo_name)
        )
        context_str, sources_str = build_context_and_sources(final_docs, expanded_map)

        # 6️⃣ Get LLM answer
        response = llm.invoke(
            prompt.format_prompt(
                context=context_str,
                sources=sources_str,
                input=query,
            ).to_messages()
        )
        answer = response.content.strip()

        return {
            "answer": answer,
            "final_docs": final_docs,
            "context": context_str,
            "sources": sources_str,
        }

    except Exception as e:
        st.error(f"❌ Error while answering: {type(e).__name__}: {e}")
        st.text(traceback.format_exc())
        return None


# ======================================================
# 💬 QUERY INTERFACE
# ======================================================
st.divider()
st.subheader("💡 Ask Questions About Your Codebase")

# Set default values for Graph-RAG pipeline
retrieval_strategy = "Graph-RAG (Knowledge Graph + Vector Search)"
enable_query_rewrite = True
graph_max_depth = 4
graph_strategy = "dfs"

query = st.text_input(
    "🔍 Your question (e.g., 'Where is judgment prediction implemented?'):",
    key="user_query",
)

run_query = st.button("🚀 Run Query", type="primary")


# ======================================================
# 🚀 GRAPH-RAG QUERY PIPELINE WITH CONTRIBUTION SUPPORT
# ======================================================
def run_graph_rag_pipeline(query: str, repo_name: str, enable_query_rewrite: bool, max_depth: int, 
                          strategy: str) -> dict:
    """Execute Graph-RAG query pipeline with contribution analysis support."""
    try:
        print("[App] Initializing contribution analyzer...")
        contrib_analyzer = load_contributions_analyzer(repo_name)
        query_understanding = get_query_understanding(repo_name)
        query_info = query_understanding.understand(query)
        
        # Check if this is a contribution-related query
        is_contribution_query = contrib_analyzer.is_contribution_query(query)
        print(f"[App] Is contribution query: {is_contribution_query}")
        print(f"[App] Query: '{query}'")
        
        if is_contribution_query:
            print("[App] 🎯 Running contribution-focused query...")
            st.info("🎯 Detected contribution query. Using git history analysis...")
            return _run_contribution_query(query, repo_name, contrib_analyzer)
        
        special_result = _route_special_intent(query, repo_name, query_info)
        if special_result:
            print(f"[App] Routed special intent: {query_info.get('intent')}")
            return special_result

        # Otherwise, run standard Graph-RAG pipeline
        print("[App] Initializing Graph-RAG retriever...")
        retriever = get_graph_rag_retriever(repo_name)
        if not retriever:
            st.error("❌ Failed to initialize Graph-RAG retriever. Check console for details.")
            return None
        
        print("[App] ✓ Retriever initialized")
        
        # Optionally rewrite query
        effective_query = rewrite_query_if_enabled(query, enable_query_rewrite)
        
        # Run Graph-RAG retrieval
        print(f"[App] Running Graph-RAG retrieval: {effective_query!r}")
        result = retriever.retrieve(
            query=effective_query,
            k_initial=5,
            max_depth=max_depth,
            strategy=strategy,
            edge_types=["calls", "called_by", "contains", "dataflow"],
            deduplicate=True
        )
        
        print(f"[App] ✓ Retrieved {len(result.final_documents)} documents")
        
        if not result.final_documents:
            st.warning("⚠️ No relevant code found. Try rephrasing your question.")
            return None
        
        # Build context for LLM
        context_parts = []
        for doc in result.final_documents:
            meta = doc.metadata or {}
            path = meta.get("path", "unknown")
            symbol = meta.get("symbol_name", "")
            lines = f"{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
            context_parts.append(f"[{path}:{symbol} lines {lines}]\n{doc.page_content}")
        
        context_str = "\n\n---\n\n".join(context_parts)
        
        # Build sources string
        sources_parts = []
        for doc in result.final_documents:
            meta = doc.metadata or {}
            path = meta.get("path", "unknown")
            symbol = meta.get("symbol_name", "")
            start = meta.get("start_line", 1)
            end = meta.get("end_line", 1)
            sources_parts.append(f"- {path}:{symbol} ({start}–{end})")
        
        sources_str = "\n".join(sources_parts) or "No sources found"
        
        # Get LLM answer
        llm = get_llm()
        response = llm.invoke(
            prompt.format_prompt(
                context=context_str,
                sources=sources_str,
                input=query,
            ).to_messages()
        )
        answer = response.content.strip()
        
        return {
            "answer": answer,
            "final_docs": result.final_documents,
            "context": context_str,
            "sources": sources_str,
            "graph_rag_result": result,
            "anchor_nodes": result.anchor_nodes,
            "total_nodes_visited": len(result.expansion_result.visited_nodes),
        }
    
    except Exception as e:
        st.error(f"❌ Error in Graph-RAG pipeline: {type(e).__name__}: {e}")
        st.text(traceback.format_exc())
        return None


def _run_contribution_query(query: str, repo_name: str, contrib_analyzer: ContributionsDataAnalyzer) -> dict:
    """Handle contribution/git history queries."""
    try:
        print("[App] Processing contribution query...")
        
        # Generate contribution context based on query
        contribution_context = contrib_analyzer.generate_contribution_context(query)
        
        if not contribution_context:
            st.warning("⚠️ No contribution data available for this repository.")
            return None
        
        # Get LLM answer using contribution prompt
        llm = get_llm()
        response = llm.invoke(
            contribution_prompt.format_prompt(
                contribution_context=contribution_context,
                input=query,
            ).to_messages()
        )
        answer = response.content.strip()
        
        # Create a minimal doc entry for display
        from langchain_core.documents import Document
        contrib_doc = Document(
            page_content=contribution_context,
            metadata={
                "path": "contribution_analysis",
                "symbol_name": "git_history",
                "start_line": 0,
                "end_line": 0,
                "parser_used": "contribution_analyzer",
                "language": "json"
            }
        )
        
        return {
            "answer": answer,
            "final_docs": [contrib_doc],
            "context": contribution_context,
            "sources": "Git Commit History",
            "is_contribution_query": True,
        }
    
    except Exception as e:
        st.error(f"❌ Error in contribution query: {type(e).__name__}: {e}")
        st.text(traceback.format_exc())
        return None



if run_query and query:
    with st.spinner("🔎 Processing your query..."):
        import time
        query_start_time = time.time()
        
        result = run_graph_rag_pipeline(
            query=query,
            repo_name=active_repo,
            enable_query_rewrite=enable_query_rewrite,
            max_depth=graph_max_depth,
            strategy=graph_strategy
        )
        
        query_latency = time.time() - query_start_time
        
        if result:
            st.session_state["last_answer"] = result["answer"]
            st.session_state["last_docs"] = result["final_docs"]
            st.session_state["last_query"] = query
            if "query_understanding" in result:
                st.session_state["intent_info"] = {
                    "intent_type": result["query_understanding"].get("intent", "unknown"),
                    "confidence": 1.0 if result["query_understanding"].get("is_startup_query") else 0.7,
                    "relevant_keywords": sorted(result["query_understanding"]["structure"].keywords),
                }
            
            # Store additional Graph-RAG info if available
            if "graph_rag_result" in result:
                st.session_state["graph_rag_result"] = result["graph_rag_result"]
                st.session_state["anchor_nodes"] = result["anchor_nodes"]
                st.session_state["total_nodes_visited"] = result["total_nodes_visited"]
            
            # ============ SAVE RETRIEVAL METRICS ============
            if save_retrieval_metrics:
                try:
                    # Extract metrics from result
                    final_docs = result.get("final_docs", [])
                    answer = result.get("answer", "")
                    intent_type = result.get("query_understanding", {}).get("intent", "unknown")
                    
                    # Method detection
                    method = "graph_rag"
                    if result.get("is_contribution_query"):
                        method = "contribution_analysis"
                    elif result.get("boot_chain_used"):
                        method = "boot_chain"
                    elif result.get("dataflow_trace_used"):
                        method = "dataflow_trace"
                    
                    # Graph expansion metrics - ensure numeric types
                    anchor_nodes_raw = result.get("anchor_nodes", 0)
                    total_visited_raw = result.get("total_nodes_visited", 0)
                    
                    # Convert to int if they're sets or other types
                    anchor_nodes = len(anchor_nodes_raw) if isinstance(anchor_nodes_raw, (set, list)) else int(anchor_nodes_raw or 0)
                    total_visited = len(total_visited_raw) if isinstance(total_visited_raw, (set, list)) else int(total_visited_raw or 0)
                    
                    graph_rag_result = result.get("graph_rag_result", {})
                    max_depth = graph_rag_result.get("max_depth_reached", 0) if isinstance(graph_rag_result, dict) else 0
                    edges_traversed = graph_rag_result.get("edges_traversed", 0) if isinstance(graph_rag_result, dict) else 0
                    
                    # Ensure numeric types
                    max_depth = int(max_depth or 0)
                    edges_traversed = int(edges_traversed or 0)
                    
                    # Diversity metrics
                    unique_files = set()
                    unique_symbols = set()
                    unique_languages = set()
                    for doc in final_docs:
                        if hasattr(doc, 'metadata'):
                            metadata = doc.metadata
                        else:
                            metadata = doc if isinstance(doc, dict) else {}
                        
                        file_path = metadata.get("file_path", "")
                        if ":" in file_path:
                            file_path = file_path.split(":", 1)[1]
                        unique_files.add(file_path)
                        
                        symbol = metadata.get("symbol", "")
                        if symbol:
                            unique_symbols.add(symbol)
                        
                        lang = metadata.get("language", "")
                        if lang:
                            unique_languages.add(lang)
                    
                    # Answer metrics
                    answer_length_chars = len(answer)
                    answer_length_words = len(answer.split())
                    
                    files_cited = len(unique_files)
                    symbols_cited = len(unique_symbols)
                    has_code_blocks = "```" in answer
                    
                    save_retrieval_metrics(
                        repo_name=active_repo,
                        query=query,
                        method=method,
                        latency_seconds=query_latency,
                        docs_returned=len(final_docs),
                        answer=answer,
                        intent_type=intent_type,
                        is_startup=result.get("query_understanding", {}).get("is_startup_query", False),
                        anchor_nodes=anchor_nodes,
                        total_visited=total_visited,
                        max_depth=max_depth,
                        edges_traversed=edges_traversed,
                        unique_files=len(unique_files),
                        unique_symbols=len(unique_symbols),
                        unique_languages=list(unique_languages),
                        answer_length_chars=answer_length_chars,
                        answer_length_words=answer_length_words,
                        files_cited=files_cited,
                        symbols_cited=symbols_cited,
                        has_code_blocks=has_code_blocks,
                    )
                except Exception as e:
                    print(f"[Evaluation] Warning: Failed to save retrieval metrics: {e}")


# ======================================================
# 📤 SHOW LAST RESULT (PERSIST ACROSS UI CHANGES)
# ======================================================
if "last_answer" in st.session_state and "last_docs" in st.session_state:
    answer = st.session_state["last_answer"]
    final_docs = st.session_state["last_docs"]
    last_query = st.session_state.get("last_query", "")

    # Show Graph-RAG statistics if available
    if "graph_rag_result" in st.session_state:
        with st.expander("📊 Graph-RAG Statistics"):
            stats = st.session_state.get("graph_rag_result").statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Anchor Nodes",
                    stats.get("initial_vector_results", 0),
                    help="Initial vector search results"
                )
            
            with col2:
                st.metric(
                    "Graph Expanded",
                    stats.get("total_nodes_visited", 0),
                    help="Total nodes reached in graph traversal"
                )
            
            with col3:
                st.metric(
                    "Max Depth",
                    stats.get("max_depth_reached", 0),
                    help="Maximum depth reached in graph traversal"
                )
            
            with col4:
                st.metric(
                    "Final Results",
                    stats.get("final_document_count", 0),
                    help="Final deduplicated documents"
                )
            
            st.markdown("**Traversal Details:**")
            st.markdown(f"- Anchor nodes: {st.session_state.get('anchor_nodes', set())}")
            st.markdown(f"- Edges traversed: {stats.get('edges_traversed', 0)}")
    
    # Show reasoning trace if available
    if "reasoning_trace" in st.session_state:
        with st.expander("🧠 Reasoning Trace"):
            st.markdown("**Multi-Step Reasoning Process:**")
            for step in st.session_state["reasoning_trace"]:
                st.markdown(f"- {step}")
    
    # Show intent and symbols if available
    if "intent_info" in st.session_state:
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("🎯 Intent Analysis"):
                intent = st.session_state["intent_info"]
                st.markdown(f"**Type:** {intent.get('intent_type', 'unknown')}")
                st.markdown(f"**Confidence:** {intent.get('confidence', 0):.1%}")
                keywords = intent.get('relevant_keywords', [])
                if keywords:
                    st.markdown(f"**Keywords:** {', '.join(keywords)}")
        
        with col2:
            if "symbols_info" in st.session_state:
                with st.expander("🔍 Identified Symbols"):
                    symbols = st.session_state["symbols_info"]
                    mentioned = symbols.get('mentioned_symbols', [])
                    inferred = symbols.get('inferred_symbols', [])
                    if mentioned:
                        st.markdown(f"**Mentioned:** {', '.join(mentioned)}")
                    if inferred:
                        st.markdown(f"**Inferred:** {', '.join(inferred)}")

    st.subheader("🤖 AI Answer")
    st.markdown(answer)

    # Show top matches
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

        # View surrounding code
        with st.expander("👁 View surrounding code"):
            seg = load_file_segment(
                m,
                repo_path=_get_repo_source_path(active_repo),
                padding=20
            )
            if seg is not None:
                segment_text, seg_start, seg_end = seg
                st.markdown(f"_Showing lines {seg_start}–{seg_end} from `{path}`_")
                st.code(segment_text, language=m.get("language") or "python")
            else:
                st.info("Unable to load surrounding file segment.")