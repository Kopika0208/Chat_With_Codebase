# ingest.py - Main ingestion pipeline orchestrator

import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# Import modular components
from .symbols import extract_python_symbols
from .dataflow import extract_function_dataflow
from .knowledge_graph import KnowledgeGraphBuilder
from .chunking import extract_chunks, EXT_TO_TS_LANG
from .callgraph import extract_python_calls, extract_js_ts_calls
from .resolver import SymbolResolver
from .utils import clone_or_open_repo, list_repo_files, get_commit_info

# ===============================
# CONFIG
# ===============================
load_dotenv()

# Get project root (parent of ingestion/ folder)
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGET_REPO_DIR = os.path.join(PROJECT_ROOT, "repos/myrepo")
VECTOR_DIR = os.path.join(PROJECT_ROOT, "data/vector_store")
CALLGRAPH_PATH = os.path.join(PROJECT_ROOT, "data/call_graph.json")
EXTENSIONS = ('.py', '.js', '.java', '.ts', '.md', '.txt', '.go', '.cpp', '.c', '.h', '.rs')
EMBED_MODEL = "mixedbread-ai/mxbai-embed-large-v1"


# ===============================
# 🚀 MAIN INGESTION PIPELINE
# ===============================
def ingest_repo(repo_url_or_path: str):
    """Main ingestion pipeline that orchestrates all modules."""
    repo_path = clone_or_open_repo(repo_url_or_path, TARGET_REPO_DIR)
    documents = []

    # Initialize analyzers and builders
    symbol_to_fqn = {}  # simple function name -> list of FQNs
    file_records = []   # (rel_path, ext, content)
    symbol_resolver = SymbolResolver()
    dataflow_by_file: Dict[str, Dict[str, Any]] = {}
    kg_builder = KnowledgeGraphBuilder()
    call_graph = {}

    print(f"🔍 Scanning repository: {repo_path}")

    # ========== FIRST PASS: CHUNKS + SYMBOL TABLE + DATA FLOW ==========
    for file_path in list_repo_files(repo_path, EXTENSIONS):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if not content.strip():
                continue

            ext = os.path.splitext(file_path)[1].lower()
            rel_path = os.path.relpath(file_path, repo_path)

            file_records.append((rel_path, ext, content))

            # Extract Python symbols using AST
            if ext == ".py":
                try:
                    symbol_table = extract_python_symbols(rel_path, content)
                    symbol_resolver.add_symbol_table(rel_path, symbol_table)
                    print(f"📊 Extracted {len(symbol_table.all_symbols)} symbols from {rel_path}")
                    
                    # Extract data flow analysis
                    dataflow_analysis = extract_function_dataflow(rel_path, content)
                    if dataflow_analysis:
                        dataflow_by_file[rel_path] = dataflow_analysis
                        print(f"🔄 Data flow analysis for {len(dataflow_analysis)} functions in {rel_path}")
                except Exception as e:
                    print(f"⚠️ Symbol/dataflow extraction failed for {rel_path}: {e}")

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
                        fqn = f"{rel_path}:{name}"
                        symbol_to_fqn.setdefault(name, []).append(fqn)

                doc_metadata = {
                    "path": rel_path,
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

    # Save call graph
    os.makedirs(os.path.dirname(CALLGRAPH_PATH), exist_ok=True)
    call_graph_serializable = {caller: list(callees) for caller, callees in call_graph.items()}
    with open(CALLGRAPH_PATH, "w", encoding="utf-8") as f:
        json.dump(call_graph_serializable, f, indent=2, ensure_ascii=False)
    print(f"📡 Saved call graph to `{CALLGRAPH_PATH}` with {len(call_graph_serializable)} caller nodes.")

    # ========== SAVE SYMBOL TABLE DATA ==========
    symbol_resolver.build_cross_references()
    symbol_table_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "symbol_table.json")
    
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

    # ========== SAVE DATA FLOW ANALYSIS ==========
    dataflow_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "dataflow_analysis.json")
    
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

    # ========== BUILD & SAVE KNOWLEDGE GRAPH ==========
    print(f"\n📚 Building comprehensive knowledge graph...")
    
    # ========== BUILD & SAVE KNOWLEDGE GRAPH ==========
    print(f"\n📚 Building comprehensive knowledge graph...")
    
    kg_builder.build_from_symbols(symbol_resolver.symbol_tables)
    print(f"✅ Added symbol nodes to knowledge graph")
    
    kg_builder.build_from_dataflow(dataflow_by_file)
    print(f"✅ Added data flow edges to knowledge graph")
    
    call_graph_for_kg = {caller: list(callees) for caller, callees in call_graph.items()}
    kg_builder.add_call_graph(call_graph_for_kg)
    print(f"✅ Added call graph edges to knowledge graph")
    
    # Export knowledge graph to JSON
    kg_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "knowledge_graph.json")
    kg_builder.export(kg_path)
    
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

    # ========== BUILD & SAVE VECTOR STORE ==========
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = FAISS.from_documents(documents, embeddings)

    os.makedirs(VECTOR_DIR, exist_ok=True)
    vectorstore.save_local(VECTOR_DIR)
    print(f"💾 Saved FAISS vector store to `{VECTOR_DIR}`")


# ===============================
# CLI
# ===============================
if __name__ == "__main__":
    repo_url = input("🔗 Enter GitHub repo URL or local path: ").strip()
    ingest_repo(repo_url)

