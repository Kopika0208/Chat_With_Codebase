# ingest.py - Main ingestion pipeline orchestrator

import os
import json

# ===============================
# CRITICAL: Define constants FIRST before any other imports
# This ensures they're always available even if other imports fail
# ===============================
# Get project root (parent of ingestion/ folder)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTENSIONS = ('.py', '.js', '.java', '.ts', '.md', '.txt', '.go', '.cpp', '.c', '.h', '.rs')
EMBED_MODEL = "mixedbread-ai/mxbai-embed-large-v1"


def _get_repo_paths(repo_name: str = None):
    """Get paths for a specific repository or default paths."""
    if repo_name:
        repo_dir = os.path.join(PROJECT_ROOT, "repos", repo_name)
        data_dir = os.path.join(PROJECT_ROOT, "data", repo_name)
    else:
        repo_dir = os.path.join(PROJECT_ROOT, "repos", "myrepo")
        data_dir = os.path.join(PROJECT_ROOT, "data")
    
    return {
        "repo_dir": repo_dir,
        "vector_dir": os.path.join(data_dir, "vector_store"),
        "callgraph_path": os.path.join(data_dir, "call_graph.json"),
        "data_dir": data_dir,
    }


# Backward compatibility: Default paths for single-repo mode
# CRITICAL: Define these BEFORE any other imports that might fail
_default_paths = _get_repo_paths(None)
VECTOR_DIR = _default_paths["vector_dir"]
CALLGRAPH_PATH = _default_paths["callgraph_path"]
TARGET_REPO_DIR = _default_paths["repo_dir"]

# Now import other modules (these may fail, but constants are already defined)
from typing import Dict, Any
try:
    from dotenv import load_dotenv
    try:
        load_dotenv()
    except Exception:
        pass  # dotenv is optional
except ImportError:
    pass  # dotenv not installed

try:
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_core.documents import Document
except ImportError:
    FAISS = None
    HuggingFaceEmbeddings = None
    Document = None

# Import modular components
try:
    from .symbols import extract_python_symbols
    from .dataflow import extract_function_dataflow
    from .knowledge_graph import KnowledgeGraphBuilder
    from .chunking import extract_chunks, EXT_TO_TS_LANG
    from .callgraph import extract_python_calls, extract_js_ts_calls
    from .resolver import SymbolResolver
    from .utils import clone_or_open_repo, list_repo_files, get_commit_info
except ImportError as e:
    # If imports fail, at least constants are available
    print(f"Warning: Some ingestion modules failed to import: {e}")
    # Define stubs to prevent NameError
    extract_python_symbols = None
    extract_function_dataflow = None
    KnowledgeGraphBuilder = None
    extract_chunks = None
    EXT_TO_TS_LANG = {}
    extract_python_calls = None
    extract_js_ts_calls = None
    SymbolResolver = None
    clone_or_open_repo = None
    list_repo_files = None
    get_commit_info = None


# ===============================
# 🚀 MAIN INGESTION PIPELINE
# ===============================
def ingest_repo(repo_url_or_path: str, repo_name: str = None, return_data: bool = False):
    """
    Main ingestion pipeline that orchestrates all modules.
    
    Args:
        repo_url_or_path: URL or local path to the repository
        repo_name: Optional name identifier for the repo (used for paths)
        return_data: If True, return the data structures instead of saving to disk
    
    Returns:
        If return_data=True, returns dict with documents, call_graph, symbol_resolver, etc.
        Otherwise returns None.
    """
    # Generate repo name from URL if not provided
    if repo_name is None:
        if repo_url_or_path.startswith("http"):
            # Extract repo name from URL (e.g., github.com/user/repo -> repo)
            repo_name = repo_url_or_path.rstrip("/").split("/")[-1].replace(".git", "")
        else:
            # Use basename of local path
            repo_name = os.path.basename(os.path.abspath(repo_url_or_path))
    
    paths = _get_repo_paths(repo_name)
    repo_path = clone_or_open_repo(repo_url_or_path, paths["repo_dir"])
    documents = []

    # Initialize analyzers and builders
    symbol_to_fqn = {}  # simple function name -> list of FQNs
    file_records = []   # (rel_path, ext, content)
    symbol_resolver = SymbolResolver()
    dataflow_by_file: Dict[str, Dict[str, Any]] = {}
    kg_builder = KnowledgeGraphBuilder()
    call_graph = {}

    print(f"🔍 Scanning repository: {repo_path} (repo_name: {repo_name})")

    # ========== FIRST PASS: CHUNKS + SYMBOL TABLE + DATA FLOW ==========
    for file_path in list_repo_files(repo_path, EXTENSIONS):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if not content.strip():
                continue

            ext = os.path.splitext(file_path)[1].lower()
            rel_path = os.path.relpath(file_path, repo_path)
            # Prefix rel_path with repo_name to avoid conflicts across repos
            prefixed_rel_path = f"{repo_name}:{rel_path}" if repo_name else rel_path

            file_records.append((prefixed_rel_path, ext, content))

            # Extract Python symbols using AST
            if ext == ".py":
                try:
                    symbol_table = extract_python_symbols(prefixed_rel_path, content)
                    symbol_resolver.add_symbol_table(prefixed_rel_path, symbol_table)
                    print(f"📊 Extracted {len(symbol_table.all_symbols)} symbols from {prefixed_rel_path}")
                    
                    # Extract data flow analysis
                    dataflow_analysis = extract_function_dataflow(prefixed_rel_path, content)
                    if dataflow_analysis:
                        dataflow_by_file[prefixed_rel_path] = dataflow_analysis
                        print(f"🔄 Data flow analysis for {len(dataflow_analysis)} functions in {prefixed_rel_path}")
                except Exception as e:
                    print(f"⚠️ Symbol/dataflow extraction failed for {prefixed_rel_path}: {e}")

            # Extract code chunks
            chunks = extract_chunks(content, ext)
            commit_sha, commit_msg, commit_date = get_commit_info(repo_path, file_path)

            for c in chunks:
                name = c.get("name")
                node_type = c.get("node_type") or ""
                language = c.get("language") or EXT_TO_TS_LANG.get(ext, ext.lstrip("."))

                # Build symbol index for functions/methods
                if name and language in ("python", "javascript", "typescript"):
                    if any(t in str(node_type).lower() for t in ["function", "method"]):
                        fqn = f"{prefixed_rel_path}:{name}"
                        symbol_to_fqn.setdefault(name, []).append(fqn)

                doc_metadata = {
                    "path": prefixed_rel_path,
                    "repo_name": repo_name,
                    "abs_path": file_path,
                    "start_line": int(c.get("start_line", 1)),
                    "end_line": int(c.get("end_line", c.get("start_line", 1))),
                    "commit_sha": commit_sha,
                    "commit_message": commit_msg,
                    "commit_date": commit_date,
                    "node_type": node_type,
                    "symbol_name": name,
                    "language": language,
                    "parser_used": c.get("parser_used", "regex_fallback"),
                    "params": c.get("params"),
                    "decorators": c.get("decorators"),
                    "imports": c.get("imports"),
                    "parent_class": c.get("parent_class"),
                }
                doc = Document(
                    page_content=c.get("text", "").strip(),
                    metadata=doc_metadata,
                )
                documents.append(doc)

            used_parser = chunks[0].get("parser_used") if chunks else "unknown"
            print(f"✅ Processed {file_path} using {used_parser} ({len(chunks)} chunks)")

        except Exception as e:
            print(f"⚠️ Skipped {file_path}: {e}")

    print(f"✅ Loaded {len(documents)} chunks total from {repo_path}")
    print(f"📚 Indexed {len(symbol_resolver.symbol_tables)} Python files with symbol tables")

    if not documents:
        print("⚠️ No documents to embed; aborting ingestion.")
        if return_data:
            return {
                "documents": [],
                "call_graph": {},
                "symbol_resolver": symbol_resolver,
                "dataflow_by_file": {},
                "kg_builder": kg_builder,
                "repo_name": repo_name,
            }
        return

    # ========== SECOND PASS: CALL GRAPH ==========
    for rel_path, ext, content in file_records:
        try:
            if ext == ".py":
                raw_calls = extract_python_calls(content)
            elif ext in (".js", ".ts"):
                raw_calls = extract_js_ts_calls(content, ext)
            else:
                raw_calls = []

            for caller_name, callee_symbol in raw_calls:
                caller_fqn = f"{rel_path}:{caller_name}"

                # Resolve callee symbol to FQN
                callee_fqn = None
                candidates = symbol_to_fqn.get(callee_symbol) or []
                if candidates:
                    callee_fqn = candidates[0]
                else:
                    callee_fqn = callee_symbol

                call_graph.setdefault(caller_fqn, set()).add(callee_fqn)
        except Exception as e:
            print(f"⚠️ Call graph extraction failed for {rel_path}: {e}")

    # ========== BUILD KNOWLEDGE GRAPH ==========
    print(f"\n📚 Building comprehensive knowledge graph...")
    
    kg_builder.build_from_symbols(symbol_resolver.symbol_tables)
    print(f"✅ Added symbol nodes to knowledge graph")
    
    kg_builder.build_from_dataflow(dataflow_by_file)
    print(f"✅ Added data flow edges to knowledge graph")
    
    call_graph_for_kg = {caller: list(callees) for caller, callees in call_graph.items()}
    kg_builder.add_call_graph(call_graph_for_kg)
    print(f"✅ Added call graph edges to knowledge graph")
    
    print(f"\n📊 Knowledge Graph Statistics:")
    print(f"   Nodes: {len(kg_builder.graph.nodes)}")
    print(f"   Edges: {len(kg_builder.graph.edges)}")
    
    # Count edges by type
    edge_types = {}
    for edge in kg_builder.graph.edges:
        edge_types[edge.edge_type] = edge_types.get(edge.edge_type, 0) + 1
    
    print(f"   Edge types:")
    for edge_type, count in sorted(edge_types.items()):
        print(f"      {edge_type}: {count}")

    # ========== BUILD VECTOR STORE ==========
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = FAISS.from_documents(documents, embeddings)

    # Return data if requested, otherwise save to disk
    if return_data:
        return {
            "documents": documents,
            "call_graph": call_graph,
            "symbol_resolver": symbol_resolver,
            "dataflow_by_file": dataflow_by_file,
            "kg_builder": kg_builder,
            "vectorstore": vectorstore,
            "repo_name": repo_name,
        }
    
    # ========== SAVE ALL DATA TO DISK ==========
    os.makedirs(paths["data_dir"], exist_ok=True)
    
    # Save call graph
    call_graph_serializable = {caller: list(callees) for caller, callees in call_graph.items()}
    with open(paths["callgraph_path"], "w", encoding="utf-8") as f:
        json.dump(call_graph_serializable, f, indent=2, ensure_ascii=False)
    print(f"📡 Saved call graph to `{paths['callgraph_path']}` with {len(call_graph_serializable)} caller nodes.")

    # Save symbol table data
    symbol_resolver.build_cross_references()
    symbol_table_path = os.path.join(paths["data_dir"], "symbol_table.json")
    
    symbol_data = {
        "global_index": symbol_resolver.export_cross_reference_graph(),
        "file_symbols": {
            file_path: symbol_table.export_to_dict()
            for file_path, symbol_table in symbol_resolver.symbol_tables.items()
        }
    }
    
    with open(symbol_table_path, "w", encoding="utf-8") as f:
        json.dump(symbol_data, f, indent=2, ensure_ascii=False)
    print(f"🏗️ Saved symbol table to `{symbol_table_path}` with {sum(len(st.all_symbols) for st in symbol_resolver.symbol_tables.values())} total symbols.")

    # Save data flow analysis
    dataflow_path = os.path.join(paths["data_dir"], "dataflow_analysis.json")
    
    with open(dataflow_path, "w", encoding="utf-8") as f:
        json.dump(dataflow_by_file, f, indent=2, ensure_ascii=False)
    
    total_functions_analyzed = sum(len(funcs) for funcs in dataflow_by_file.values())
    print(f"📊 Saved data flow analysis for {total_functions_analyzed} functions to `{dataflow_path}`")
    
    total_def_use_chains = sum(
        len(func_analysis.get("def_use_chains", {}))
        for file_funcs in dataflow_by_file.values()
        for func_analysis in file_funcs.values()
    )
    print(f"🔗 Tracked {total_def_use_chains} definition-use chains across all functions")

    # Export knowledge graph to JSON
    kg_path = os.path.join(paths["data_dir"], "knowledge_graph.json")
    kg_builder.export(kg_path)

    # Save vector store
    os.makedirs(paths["vector_dir"], exist_ok=True)
    vectorstore.save_local(paths["vector_dir"])
    print(f"💾 Saved FAISS vector store to `{paths['vector_dir']}`")


# ===============================
# MULTI-REPO INGESTION
# ===============================
def ingest_repos(repo_list: list, aggregate: bool = True):
    """
    Ingest multiple repositories and optionally aggregate the results.
    
    Args:
        repo_list: List of tuples (repo_url_or_path, repo_name) or just repo URLs/paths
        aggregate: If True, merge all data into unified stores. If False, keep separate.
    
    Returns:
        Dict with aggregated data if aggregate=True, otherwise list of per-repo data
    """
    all_documents = []
    all_call_graphs = {}
    all_symbol_resolvers = []
    all_dataflow = {}
    all_kg_builders = []
    all_vectorstores = []
    repo_names = []
    
    # Process each repository
    for i, repo_item in enumerate(repo_list):
        if isinstance(repo_item, tuple):
            repo_url_or_path, repo_name = repo_item
        else:
            repo_url_or_path = repo_item
            repo_name = None
        
        print(f"\n{'='*60}")
        print(f"📦 Processing repository {i+1}/{len(repo_list)}: {repo_url_or_path}")
        print(f"{'='*60}\n")
        
        result = ingest_repo(repo_url_or_path, repo_name=repo_name, return_data=True)
        
        if result:
            all_documents.extend(result["documents"])
            all_call_graphs.update(result["call_graph"])
            all_symbol_resolvers.append(result["symbol_resolver"])
            all_dataflow.update(result["dataflow_by_file"])
            all_kg_builders.append(result["kg_builder"])
            all_vectorstores.append(result["vectorstore"])
            repo_names.append(result["repo_name"])
    
    if not aggregate:
        print("\n✅ All repositories processed separately.")
        return {
            "repos": repo_names,
            "per_repo_data": [
                {
                    "repo_name": name,
                    "documents_count": len([d for d in all_documents if d.metadata.get("repo_name") == name]),
                }
                for name in repo_names
            ]
        }
    
    # Aggregate data
    print(f"\n{'='*60}")
    print(f"🔄 Aggregating data from {len(repo_list)} repositories...")
    print(f"{'='*60}\n")
    
    # Merge symbol resolvers
    aggregated_symbol_resolver = SymbolResolver()
    for sr in all_symbol_resolvers:
        for file_path, symbol_table in sr.symbol_tables.items():
            aggregated_symbol_resolver.add_symbol_table(file_path, symbol_table)
    aggregated_symbol_resolver.build_cross_references()
    
    # Merge knowledge graphs
    aggregated_kg = KnowledgeGraphBuilder()
    for kg_builder in all_kg_builders:
        # Add all nodes and edges from each knowledge graph
        for node in kg_builder.graph.nodes.values():
            aggregated_kg.graph.add_node(node)
        for edge in kg_builder.graph.edges:
            aggregated_kg.graph.add_edge(edge)
    
    # Merge vector stores
    print("💾 Merging vector stores...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    # Create a new vectorstore from all documents (FAISS doesn't have merge_from)
    merged_vectorstore = FAISS.from_documents(all_documents, embeddings)
    
    # Save aggregated data
    aggregated_paths = _get_repo_paths(None)  # Use default paths for aggregated data
    os.makedirs(aggregated_paths["data_dir"], exist_ok=True)
    
    # Save aggregated call graph
    with open(aggregated_paths["callgraph_path"], "w", encoding="utf-8") as f:
        json.dump({caller: list(callees) for caller, callees in all_call_graphs.items()}, 
                 f, indent=2, ensure_ascii=False)
    print(f"📡 Saved aggregated call graph with {len(all_call_graphs)} caller nodes.")
    
    # Save aggregated symbol table
    symbol_table_path = os.path.join(aggregated_paths["data_dir"], "symbol_table.json")
    symbol_data = {
        "global_index": aggregated_symbol_resolver.export_cross_reference_graph(),
        "file_symbols": {
            file_path: symbol_table.export_to_dict()
            for file_path, symbol_table in aggregated_symbol_resolver.symbol_tables.items()
        }
    }
    with open(symbol_table_path, "w", encoding="utf-8") as f:
        json.dump(symbol_data, f, indent=2, ensure_ascii=False)
    print(f"🏗️ Saved aggregated symbol table with {sum(len(st.all_symbols) for st in aggregated_symbol_resolver.symbol_tables.values())} total symbols.")
    
    # Save aggregated dataflow
    dataflow_path = os.path.join(aggregated_paths["data_dir"], "dataflow_analysis.json")
    with open(dataflow_path, "w", encoding="utf-8") as f:
        json.dump(all_dataflow, f, indent=2, ensure_ascii=False)
    print(f"📊 Saved aggregated data flow analysis.")
    
    # Save aggregated knowledge graph
    kg_path = os.path.join(aggregated_paths["data_dir"], "knowledge_graph.json")
    aggregated_kg.export(kg_path)
    print(f"📚 Saved aggregated knowledge graph with {len(aggregated_kg.graph.nodes)} nodes and {len(aggregated_kg.graph.edges)} edges.")
    
    # Save aggregated vector store
    os.makedirs(aggregated_paths["vector_dir"], exist_ok=True)
    merged_vectorstore.save_local(aggregated_paths["vector_dir"])
    print(f"💾 Saved aggregated FAISS vector store with {len(all_documents)} documents.")
    
    print(f"\n✅ Successfully aggregated {len(repo_list)} repositories!")
    return {
        "repos": repo_names,
        "total_documents": len(all_documents),
        "total_call_graph_nodes": len(all_call_graphs),
        "total_symbols": sum(len(st.all_symbols) for st in aggregated_symbol_resolver.symbol_tables.values()),
        "kg_nodes": len(aggregated_kg.graph.nodes),
        "kg_edges": len(aggregated_kg.graph.edges),
    }


# ===============================
# CLI
# ===============================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Multiple repos provided as arguments
        repos = sys.argv[1:]
        print(f"📦 Processing {len(repos)} repositories...")
        result = ingest_repos(repos, aggregate=True)
        print(f"\n✅ Completed! Processed {len(repos)} repositories.")
    else:
        # Single repo interactive mode
        repo_url = input("🔗 Enter GitHub repo URL or local path: ").strip()
        ingest_repo(repo_url)

