# app.py
"""
Main Streamlit application for Chat with Codebase.
Handles UI, LLM integration, and orchestrates retrieval modules.
"""
import sys, os
# Force add project root (parent of retrieval/) to PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

print("DEBUG: USING PROJECT ROOT =", PROJECT_ROOT)
print("DEBUG: CURRENT WORKING DIRECTORY =", os.getcwd())

# ===============================
# 📂 MULTI-REPO SUPPORT
# ===============================
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

def list_ingested_repos():
    """List all ingested repositories from the data directory."""
    if not os.path.exists(DATA_DIR):
        return []
    return sorted(
        d for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d))
    )

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
    get_graph_rag_retriever,
    load_knowledge_graph_cached,
    load_graph_traversal_cached,
    load_symbol_table_cached,
    load_dataflow_data_cached,
    get_unified_retriever,
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

# ===============================
# ⚙️ SETUP
# ===============================
load_dotenv()
st.set_page_config(page_title="Chat with Your Codebase", layout="wide")
st.title("💬 Chat with Your Codebase – Multi-Repo + Multi-Hop + Call Graph")

LANGCHAIN_PROJECT = "chat-with-codebase"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT

try:
    client = Client()
    print(f"✅ LangSmith connected: {client.api_url}")
except Exception:
    print("⚠️ LangSmith inactive")

# Initialize session state for multi-repo support
if "active_repo" not in st.session_state:
    st.session_state["active_repo"] = None

if "last_active_repo" not in st.session_state:
    st.session_state["last_active_repo"] = None


# ===============================
# 🧠 LLM PROMPT TEMPLATE
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
            get_graph_rag_retriever.clear()
            load_knowledge_graph_cached.clear()
            load_graph_traversal_cached.clear()
            load_symbol_table_cached.clear()
            load_dataflow_data_cached.clear()
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
            get_graph_rag_retriever.clear()
            load_knowledge_graph_cached.clear()
            load_graph_traversal_cached.clear()
            load_symbol_table_cached.clear()
            load_dataflow_data_cached.clear()
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

except Exception as e:
    st.error(f"❌ Error initializing onboarding module: {type(e).__name__}: {e}")
    print(traceback.format_exc())


# ======================================================
# 🔌 QUERY PROCESSING PIPELINE
# ======================================================
def run_query_pipeline(query: str, repo_name: str, enable_query_rewrite: bool, enable_multi_hop: bool,
                      enable_reasoning_chain: bool, k: int = 10) -> dict:
    """Execute the complete query pipeline."""
    
    # Check if reasoning chain should be used
    if enable_reasoning_chain:
        try:
            reasoning_chain = get_reasoning_chain()
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
            repo_path=os.path.join("repos", repo_name)
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

# Retrieval strategy selection
retrieval_strategy = st.radio(
    "🔄 Choose retrieval strategy:",
    ["Semantic + Multi-hop", "Graph-RAG (Knowledge Graph + Vector Search)"],
    help="Semantic: Traditional vector search with call graph. Graph-RAG: Knowledge graph with intelligent expansion.",
)

enable_query_rewrite = st.checkbox(
    "✏️ Enable smart query rewriting (improves search)",
    value=True,
)

if retrieval_strategy == "Graph-RAG (Knowledge Graph + Vector Search)":
    col1, col2 = st.columns(2)
    with col1:
        graph_max_depth = st.slider("📊 Graph traversal depth:", 1, 4, 2)
    with col2:
        graph_strategy = st.selectbox("📈 Traversal strategy:", ["bfs", "dfs"])
else:
    enable_multi_hop = st.checkbox(
        "🔁 Enable multi-hop retrieval (follow related files/symbols)",
        value=True,
    )
    
    enable_reasoning_chain = st.checkbox(
        "🧠 Enable multi-step reasoning chain (advanced reasoning)",
        value=False,
    )

query = st.text_input(
    "🔍 Your question (e.g., 'Where is judgment prediction implemented?'):",
    key="user_query",
)

run_query = st.button("🚀 Run Query", type="primary")


# ======================================================
# 🚀 GRAPH-RAG QUERY PIPELINE
# ======================================================
def run_graph_rag_pipeline(query: str, repo_name: str, enable_query_rewrite: bool, max_depth: int, 
                          strategy: str) -> dict:
    """Execute Graph-RAG query pipeline."""
    try:
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



if run_query and query:
    with st.spinner("🔎 Processing your query..."):
        if retrieval_strategy == "Graph-RAG (Knowledge Graph + Vector Search)":
            result = run_graph_rag_pipeline(
                query=query,
                repo_name=active_repo,
                enable_query_rewrite=enable_query_rewrite,
                max_depth=graph_max_depth,
                strategy=graph_strategy
            )
        else:
            result = run_query_pipeline(
                query=query,
                repo_name=active_repo,
                enable_query_rewrite=enable_query_rewrite,
                enable_multi_hop=enable_multi_hop,
                enable_reasoning_chain=enable_reasoning_chain,
                k=10
            )
        
        if result:
            st.session_state["last_answer"] = result["answer"]
            st.session_state["last_docs"] = result["final_docs"]
            st.session_state["last_query"] = query
            
            # Store additional Graph-RAG info if available
            if "graph_rag_result" in result:
                st.session_state["graph_rag_result"] = result["graph_rag_result"]
                st.session_state["anchor_nodes"] = result["anchor_nodes"]
                st.session_state["total_nodes_visited"] = result["total_nodes_visited"]
            
            if "intent_info" in result:
                st.session_state["intent_info"] = result["intent_info"]
            if "symbols_info" in result:
                st.session_state["symbols_info"] = result["symbols_info"]
            if "reasoning_trace" in result:
                st.session_state["reasoning_trace"] = result["reasoning_trace"]


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
                repo_path=os.path.join("repos", active_repo),
                padding=20
            )
            if seg is not None:
                segment_text, seg_start, seg_end = seg
                st.markdown(f"_Showing lines {seg_start}–{seg_end} from `{path}`_")
                st.code(segment_text, language=m.get("language") or "python")
            else:
                st.info("Unable to load surrounding file segment.")


