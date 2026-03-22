# ingest.py - Main ingestion pipeline orchestrator

import gc
import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Dict, List, Optional

# ===============================
# Import core ingestion modules
# ===============================
try:
    from .chunking import extract_chunks
except ImportError:
    extract_chunks = None

try:
    from .resolver import SymbolResolver
except ImportError:
    SymbolResolver = None

try:
    from .knowledge_graph import KnowledgeGraphBuilder
except ImportError:
    KnowledgeGraphBuilder = None

try:
    from .utils import clone_or_open_repo, get_repo_head_info, list_repo_files
except ImportError:
    clone_or_open_repo = None
    get_repo_head_info = None
    list_repo_files = None

try:
    from .symbols import extract_symbols_unified
except ImportError:
    extract_symbols_unified = None

try:
    from .semantic_analyzer import extract_function_dataflow, extract_async_patterns
except ImportError:
    extract_function_dataflow = None
    extract_async_patterns = None

try:
    from .contributions import extract_contributions
except ImportError:
    extract_contributions = None

try:
    from .chunking import EXT_TO_TS_LANG, Document
except ImportError:
    EXT_TO_TS_LANG = {}
    Document = None

try:
    from .callgraph import extract_calls_unified
except ImportError:
    extract_calls_unified = None

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
except ImportError:
    HuggingFaceEmbeddings = None
    FAISS = None

try:
    from .zip_ingestion import download_and_extract_repo
except ImportError:
    download_and_extract_repo = None

try:
    from .github_loader import get_repo_metadata
except ImportError:
    get_repo_metadata = None

try:
    from evaluation.collector import save_ingestion_metrics, save_contribution_metrics, save_graph_metrics
except ImportError:
    save_ingestion_metrics = None
    save_contribution_metrics = None
    save_graph_metrics = None

# ===============================
# CRITICAL: Define constants FIRST before any other imports
# This ensures they're always available even if other imports fail
# ===============================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTENSIONS = (".py", ".js", ".java", ".ts", ".md", ".txt", ".go", ".cpp", ".c", ".h", ".rs")
EMBED_MODEL = "mixedbread-ai/mxbai-embed-large-v1"
BOOT_ENTRY_CANDIDATES = ("main", "app", "run", "start", "__main__")
SUPPORTED_ANALYSIS_EXTENSIONS = {
    ".py", ".java", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs"
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


EMBED_BATCH_SIZE = max(16, _env_int("INGEST_EMBED_BATCH_SIZE", 128))
FILE_WORKERS = max(1, _env_int("INGEST_FILE_WORKERS", min(8, (os.cpu_count() or 4))))
MAX_IN_FLIGHT_FILES = max(FILE_WORKERS, _env_int("INGEST_MAX_IN_FLIGHT_FILES", FILE_WORKERS * 2))
PROGRESS_LOG_EVERY = max(1, _env_int("INGEST_PROGRESS_EVERY", 25))
GC_COLLECT_EVERY = max(0, _env_int("INGEST_GC_COLLECT_EVERY", 100))
ENABLE_CONTRIBUTION_ANALYSIS_BY_DEFAULT = _env_bool("INGEST_ANALYZE_CONTRIBUTIONS", False)
CONTRIBUTION_MAX_COMMITS = max(0, _env_int("INGEST_CONTRIBUTION_MAX_COMMITS", 500))
CONTRIBUTION_INCLUDE_DETAILS = _env_bool("INGEST_CONTRIBUTION_INCLUDE_DETAILS", True)

# ===============================
# API vs ZIP INGESTION THRESHOLDS
# ===============================
MAX_API_FILES = _env_int("MAX_API_FILES", 1500)
MAX_API_SIZE_MB = _env_int("MAX_API_SIZE_MB", 50)
MAX_API_ESTIMATED_CALLS = _env_int("MAX_API_ESTIMATED_CALLS", 2000)


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
        "bootchain_path": os.path.join(data_dir, "boot_chain.json"),
        "corestructures_path": os.path.join(data_dir, "core_structures.json"),
        "asyncpatterns_path": os.path.join(data_dir, "async_patterns.json"),
        "data_dir": data_dir,
    }


def _build_symbol_metadata(symbol_resolver) -> Dict[str, Dict[str, Any]]:
    """Flatten symbol table data for later boot-sequence summaries."""
    symbol_metadata: Dict[str, Dict[str, Any]] = {}

    if not symbol_resolver:
        return symbol_metadata

    for file_path, symbol_table in symbol_resolver.symbol_tables.items():
        for fqn, symbol in symbol_table.all_symbols.items():
            symbol_metadata[fqn] = {
                "name": symbol.name,
                "kind": symbol.kind,
                "file": file_path,
                "line": symbol.line_number,
                "end_line": symbol.end_line,
                "scope_id": symbol.scope_id,
            }

    return symbol_metadata


def _select_boot_entry_points(call_graph: Dict[str, set], symbol_metadata: Dict[str, Dict[str, Any]]) -> list:
    """Choose likely startup roots using explicit names, then fall back to graph heuristics."""
    inbound_counts: Dict[str, int] = {}
    for caller, callees in call_graph.items():
        inbound_counts.setdefault(caller, 0)
        for callee in callees:
            inbound_counts[callee] = inbound_counts.get(callee, 0) + 1

    named_entries = []
    for fqn in call_graph.keys():
        short_name = (symbol_metadata.get(fqn, {}).get("name") or fqn.split(":")[-1]).lower()
        if short_name in BOOT_ENTRY_CANDIDATES:
            named_entries.append(fqn)

    if named_entries:
        return named_entries

    scored = []
    for fqn, callees in call_graph.items():
        short_name = (symbol_metadata.get(fqn, {}).get("name") or fqn.split(":")[-1]).lower()
        in_degree = inbound_counts.get(fqn, 0)
        out_degree = len(callees)
        if out_degree <= 0:
            continue

        looks_like_entry = any(token in short_name for token in BOOT_ENTRY_CANDIDATES)
        score = (4 if looks_like_entry else 0) + min(out_degree, 5) - min(in_degree, 3)
        scored.append((score, in_degree, -out_degree, fqn))

    scored.sort(reverse=True)
    return [fqn for _, _, _, fqn in scored[:5]]


def _build_boot_chain(call_graph: Dict[str, set], symbol_metadata: Dict[str, Dict[str, Any]], repo_name: str) -> Dict[str, Any]:
    """Pre-compute a startup summary from likely entry points."""
    if not call_graph:
        return {
            "repo_name": repo_name,
            "entry_points": [],
            "ordered_steps": [],
            "ready_candidates": [],
            "graph": {},
            "summary": "No call graph data was available to derive a boot sequence.",
        }

    entry_points = _select_boot_entry_points(call_graph, symbol_metadata)
    if not entry_points:
        return {
            "repo_name": repo_name,
            "entry_points": [],
            "ordered_steps": [],
            "ready_candidates": [],
            "graph": {},
            "summary": "No reliable startup entry points were found in the call graph.",
        }

    visited = set()
    queue = [(entry, 0, None) for entry in entry_points]
    ordered_steps = []
    graph = {}
    ready_candidates = []

    while queue:
        node, depth, parent = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)

        callees = sorted(call_graph.get(node, []))
        meta = symbol_metadata.get(node, {})
        record = {
            "fqn": node,
            "name": meta.get("name") or node.split(":")[-1],
            "kind": meta.get("kind", "unknown"),
            "file": meta.get("file", node.split(":")[0] if ":" in node else "unknown"),
            "line": meta.get("line", 0),
            "end_line": meta.get("end_line", 0),
            "depth": depth,
            "called_by": parent,
            "callees": callees,
            "callee_count": len(callees),
            "is_entry": node in entry_points,
        }
        ordered_steps.append(record)
        graph[node] = callees

        lower_name = record["name"].lower()
        if depth > 0 and (
            len(callees) == 0
            or any(token in lower_name for token in ("ready", "listen", "serve", "mount", "init", "setup"))
        ):
            ready_candidates.append(record)

        for callee in callees:
            if callee not in visited:
                queue.append((callee, depth + 1, node))

    ordered_steps.sort(key=lambda item: (item["depth"], item["file"], item["line"], item["name"]))
    ready_candidates.sort(key=lambda item: (item["depth"], item["name"]))

    return {
        "repo_name": repo_name,
        "entry_points": [step for step in ordered_steps if step["is_entry"]],
        "ordered_steps": ordered_steps,
        "ready_candidates": ready_candidates[:10],
        "graph": graph,
        "summary": (
            f"Derived boot sequence from {len(entry_points)} entry point(s) "
            f"covering {len(ordered_steps)} reachable symbol(s)."
        ),
    }


def _build_core_structures(symbol_resolver, kg_builder, repo_name: str) -> Dict[str, Any]:
    """Pre-compute classes that appear to own the most state or child symbols."""
    if not symbol_resolver or not kg_builder:
        return {
            "repo_name": repo_name,
            "structures": [],
            "summary": "No symbol or graph data was available to derive core structures.",
        }

    graph = kg_builder.graph
    contains_counts: Dict[str, int] = {}
    child_symbols: Dict[str, list] = {}

    for edge in graph.edges:
        if edge.edge_type != "contains":
            continue
        contains_counts[edge.source_id] = contains_counts.get(edge.source_id, 0) + 1
        target = graph.nodes.get(edge.target_id)
        if target:
            child_symbols.setdefault(edge.source_id, []).append({
                "id": edge.target_id,
                "name": target.name,
                "type": target.node_type,
                "file": target.file_path,
                "line": target.line_number,
            })

    structures = []
    for node_id, node in graph.nodes.items():
        if node.node_type != "class":
            continue
        structures.append({
            "id": node_id,
            "name": node.name,
            "file": node.file_path,
            "line": node.line_number,
            "contained_symbol_count": contains_counts.get(node_id, 0),
            "children": sorted(
                child_symbols.get(node_id, []),
                key=lambda child: (child["type"], child["name"]),
            )[:25],
        })

    structures.sort(key=lambda item: (-item["contained_symbol_count"], item["name"], item["file"]))
    return {
        "repo_name": repo_name,
        "structures": structures[:20],
        "summary": f"Identified {len(structures)} class-based data structures ranked by contained symbol count.",
    }


_default_paths = _get_repo_paths(None)
VECTOR_DIR = _default_paths["vector_dir"]
CALLGRAPH_PATH = _default_paths["callgraph_path"]
TARGET_REPO_DIR = _default_paths["repo_dir"]

try:
    from dotenv import load_dotenv

    try:
        load_dotenv()
    except Exception:
        pass
except ImportError:
    pass

try:
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    FAISS = None
    Document = None
    HuggingFaceEmbeddings = None

try:
    from .async_extractor import extract_async_patterns
    from .callgraph import extract_calls_unified
    from .chunking import EXT_TO_TS_LANG, extract_chunks
    from .contributions import extract_contributions
    from .dataflow import extract_function_dataflow
    from .knowledge_graph import KnowledgeGraphBuilder
    from .resolver import SymbolResolver
    from .symbols import extract_symbols_unified
    from .utils import clone_or_open_repo, get_repo_head_info, list_repo_files
    from .github_loader import get_repo_metadata
    from .zip_ingestion import download_and_extract_repo, cleanup_zip_extraction, list_files_from_zip
    from .github_contributions import extract_contributions_via_api, save_contributions
except ImportError as e:
    print(f"Warning: Some ingestion modules failed to import: {e}")
    extract_async_patterns = None
    extract_calls_unified = None
    EXT_TO_TS_LANG = {}
    extract_chunks = None
    extract_contributions = None
    extract_function_dataflow = None
    KnowledgeGraphBuilder = None
    SymbolResolver = None
    extract_symbols_unified = None
    clone_or_open_repo = None
    get_repo_head_info = None
    list_repo_files = None
    get_repo_metadata = None
    download_and_extract_repo = None
    cleanup_zip_extraction = None
    list_files_from_zip = None
    extract_contributions_via_api = None
    save_contributions = None


def _file_priority(file_path: str, repo_path: str):
    """Prioritize likely entry/config files and smaller files first."""
    rel_path = os.path.relpath(file_path, repo_path).replace("\\", "/").lower()
    base_name = os.path.basename(file_path).lower()
    important_names = (
        "main.py", "app.py", "__main__.py", "index.js", "main.js", "app.js",
        "package.json", "pyproject.toml", "setup.py", "manage.py", "dockerfile",
        "requirements.txt", "tsconfig.json", "vite.config.ts", "next.config.js",
    )

    priority = 2
    if base_name in important_names:
        priority = 0
    elif any(token in rel_path for token in ("config", "settings", "routes", "server", "entry", "main", "app")):
        priority = 1

    try:
        size = os.path.getsize(file_path)
    except OSError:
        size = 0

    return (priority, size, rel_path)


def _parse_github_url(repo_url: str) -> tuple:
    """Parse GitHub URL to extract owner/repo. Returns (owner, repo) or (None, None)."""
    if not isinstance(repo_url, str) or "github.com" not in repo_url.lower():
        return None, None
    
    try:
        if "github.com/" in repo_url:
            parts = repo_url.split("github.com/")[1].split("/")
        elif "github.com:" in repo_url:
            parts = repo_url.split("github.com:")[1].split("/")
        else:
            return None, None
        
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "").strip()
    except:
        pass
    
    return None, None


def _should_use_zip(owner: str, repo: str, token: Optional[str]) -> tuple:
    """Check if repo size exceeds API thresholds, requiring ZIP ingestion.
    
    Returns:
        (use_zip: bool, default_branch: str)
    """
    default_branch = "main"
    try:
        if not get_repo_metadata:
            return False, default_branch
        
        metadata = get_repo_metadata(owner, repo, token=token)
        if not metadata or "size" not in metadata:
            return False, default_branch
        
        default_branch = metadata.get("default_branch", "main")
        size_kb = metadata.get("size", 0)
        size_mb = size_kb / 1024 if size_kb else 0
        estimated_files = int(size_kb * 0.0003) if size_kb else 0
        estimated_calls = estimated_files + 10
        
        print(f"\n[Repo Analysis] Size: {size_mb:.1f}MB, Files: {estimated_files}, API calls: {estimated_calls}")
        print(f"  Default branch: {default_branch}")
        
        if size_mb > MAX_API_SIZE_MB:
            print(f"  [Using ZIP] Size exceeds {MAX_API_SIZE_MB}MB")
            return True, default_branch
        if estimated_files > MAX_API_FILES:
            print(f"  [Using ZIP] Files exceed {MAX_API_FILES}")
            return True, default_branch
        if estimated_calls > MAX_API_ESTIMATED_CALLS:
            print(f"  [Using ZIP] API calls exceed {MAX_API_ESTIMATED_CALLS}")
            return True, default_branch
        
        print(f"  [Using API] Within all thresholds")
        return False, default_branch
    except Exception as e:
        print(f"  [Note] Analysis failed ({e}), defaulting to API")
        return False, default_branch


def _format_duration(seconds: float) -> str:
    """Format duration to human-readable string."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.2f}m"
    else:
        return f"{seconds / 3600:.2f}h"


def _process_repo_file(
    file_path: str,
    repo_path: str,
    repo_name: str,
    repo_commit_sha: str,
    repo_commit_msg: str,
    repo_commit_date: Optional[str],
) -> Dict[str, Any]:
    """Process a single file and return all extracted artifacts."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
        content = handle.read()

    if not content.strip():
        return {"skip": True, "file_path": file_path}

    ext = os.path.splitext(file_path)[1].lower()
    rel_path = os.path.relpath(file_path, repo_path)
    prefixed_rel_path = f"{repo_name}:{rel_path}" if repo_name else rel_path

    result: Dict[str, Any] = {
        "skip": False,
        "file_path": file_path,
        "ext": ext,
        "prefixed_rel_path": prefixed_rel_path,
        "chunks": [],
        "documents": [],
        "symbol_table": None,
        "dataflow_analysis": None,
        "async_analysis": None,
        "raw_calls": [],
        "used_parser": "unknown",
    }

    if ext in SUPPORTED_ANALYSIS_EXTENSIONS:
        if extract_symbols_unified:
            result["symbol_table"] = extract_symbols_unified(prefixed_rel_path, content)

        if ext == ".py" and extract_function_dataflow:
            result["dataflow_analysis"] = extract_function_dataflow(prefixed_rel_path, content)

        if ext == ".py" and extract_async_patterns:
            result["async_analysis"] = extract_async_patterns(prefixed_rel_path, content)

        if extract_calls_unified:
            result["raw_calls"] = extract_calls_unified(content, ext)

    chunks = extract_chunks(content, ext)
    result["chunks"] = chunks
    result["used_parser"] = chunks[0].get("parser_used") if chunks else "unknown"

    for chunk in chunks:
        name = chunk.get("name")
        node_type = chunk.get("node_type") or ""
        language = chunk.get("language") or EXT_TO_TS_LANG.get(ext, ext.lstrip("."))
        result["documents"].append(
            Document(
                page_content=chunk.get("text", "").strip(),
                metadata={
                    "path": prefixed_rel_path,
                    "repo_name": repo_name,
                    "abs_path": file_path,
                    "start_line": int(chunk.get("start_line", 1)),
                    "end_line": int(chunk.get("end_line", chunk.get("start_line", 1))),
                    "commit_sha": repo_commit_sha,
                    "commit_message": repo_commit_msg,
                    "commit_date": repo_commit_date,
                    "node_type": node_type,
                    "symbol_name": name,
                    "language": language,
                    "parser_used": chunk.get("parser_used", "regex_fallback"),
                    "params": chunk.get("params"),
                    "decorators": chunk.get("decorators"),
                    "imports": chunk.get("imports"),
                    "parent_class": chunk.get("parent_class"),
                },
            )
        )

    del content
    return result


def _drain_completed_futures(futures, max_items: Optional[int] = None):
    """Yield completed futures while keeping the backlog bounded."""
    emitted = 0
    while futures and (max_items is None or emitted < max_items):
        done, _ = wait(list(futures.keys()), return_when=FIRST_COMPLETED)
        for future in done:
            file_path = futures.pop(future)
            emitted += 1
            yield file_path, future
            if max_items is not None and emitted >= max_items:
                return


def ingest_repo(
    repo_url_or_path: str,
    repo_name: str = None,
    return_data: bool = False,
    analyze_contributions: Optional[bool] = None,
    contribution_commit_limit: Optional[int] = None,
    verbose: bool = False,
):
    """Main ingestion pipeline: API by default, ZIP if size thresholds exceeded."""
    import time
    import tempfile
    
    overall_start_time = time.time()
    
    if repo_name is None:
        if repo_url_or_path.startswith("http"):
            repo_name = repo_url_or_path.rstrip("/").split("/")[-1].replace(".git", "")
        else:
            repo_name = os.path.basename(os.path.abspath(repo_url_or_path))

    if not all([extract_chunks, SymbolResolver, KnowledgeGraphBuilder]):
        raise RuntimeError("Required ingestion modules are not available.")

    # ============ REPO LOADING PHASE ============
    load_start_time = time.time()
    
    paths = _get_repo_paths(repo_name)
    repo_path = None
    zip_cleanup_root = None
    ingestion_method = "API"
    github_token = os.getenv("GITHUB_TOKEN")
    
    owner, repo = _parse_github_url(repo_url_or_path)
    
    # Default to API; switch to ZIP only if thresholds exceeded
    default_branch = "main"
    use_zip = False
    if owner and repo:
        use_zip, default_branch = _should_use_zip(owner, repo, github_token)
    
    try:
        if use_zip:
            # ZIP ingestion for large repos
            try:
                print(f"\n[ZIP] Downloading {owner}/{repo} ({default_branch})...")
                repo_path, _, zip_cleanup_root = download_and_extract_repo(owner, repo, default_branch, github_token)
                print(f"[ZIP] Repository extracted")
                ingestion_method = "ZIP"
            except Exception as e:
                print(f"[ZIP] Failed: {e}. Falling back to API...")
                use_zip = False
        
        if not use_zip and not repo_path:
            # API ingestion (default)
            if owner and repo:
                try:
                    from .github_loader import get_repo_tree, get_file_content
                    
                    print(f"\n[API] Fetching {owner}/{repo} ({default_branch})...")
                    repo_path = tempfile.mkdtemp(prefix=f"{repo}_")
                    zip_cleanup_root = repo_path
                    
                    files_to_fetch = get_repo_tree(owner, repo, default_branch, token=github_token)
                    print(f"[API] Found {len(files_to_fetch)} files, downloading...")
                    
                    fetched_count = 0
                    skipped_count = 0
                    failed_count = 0
                    
                    # Import path-only filter from api_ingestion (doesn't need file on disk)
                    from .api_ingestion import _path_is_supported
                    
                    for file_entry in files_to_fetch:
                        file_path = file_entry.get("path")
                        if not file_path:
                            continue
                        
                        # Filter by path/extension/size BEFORE downloading
                        # (should_skip needs the file on disk; _path_is_supported does not)
                        if not _path_is_supported(file_path, file_entry.get("size")):
                            skipped_count += 1
                            continue
                        
                        temp_full_path = os.path.join(repo_path, file_path)
                        os.makedirs(os.path.dirname(temp_full_path), exist_ok=True)
                        try:
                            content = get_file_content(owner, repo, file_path, default_branch, token=github_token)
                            with open(temp_full_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            fetched_count += 1
                        except Exception as e:
                            failed_count += 1
                            if verbose:
                                print(f"[API] Failed to fetch {file_path}: {e}")
                    
                    print(f"[API] Downloaded {fetched_count} files (skipped {skipped_count}, failed {failed_count})")
                    ingestion_method = "API"
                except Exception as e:
                    print(f"[API] Failed: {e}")
                    if zip_cleanup_root and os.path.exists(zip_cleanup_root):
                        import shutil
                        shutil.rmtree(zip_cleanup_root, ignore_errors=True)
                        zip_cleanup_root = None
                    raise
            else:
                # Fallback to git clone for non-GitHub URLs
                if clone_or_open_repo:
                    print(f"\n[Git Clone] Cloning repository...")
                    repo_path = clone_or_open_repo(repo_url_or_path, paths["repo_dir"])
                    ingestion_method = "git_clone"
                else:
                    raise RuntimeError("Cannot ingest non-GitHub URL without git clone support")
    
    except Exception as e:
        print(f"Error during repo loading: {e}")
        raise
    
    load_duration = time.time() - load_start_time
    
    repo_commit_sha, repo_commit_msg, repo_commit_date = (
        get_repo_head_info(repo_path) if get_repo_head_info else ("unknown", "No commit message found", None)
    )
    analyze_contributions = (
        ENABLE_CONTRIBUTION_ANALYSIS_BY_DEFAULT if analyze_contributions is None else analyze_contributions
    )
    contribution_commit_limit = (
        CONTRIBUTION_MAX_COMMITS if contribution_commit_limit is None else contribution_commit_limit
    )

    all_documents = [] if return_data else None
    pending_documents: List[Document] = []
    raw_call_records: List[tuple] = []

    symbol_to_fqn = {}
    symbol_resolver = SymbolResolver()
    dataflow_by_file: Dict[str, Dict[str, Any]] = {}
    async_patterns_by_file: Dict[str, Dict[str, Any]] = {}
    kg_builder = KnowledgeGraphBuilder()
    call_graph = {}

    embeddings = None
    vectorstore = None
    total_documents = 0

    def flush_document_batch():
        nonlocal embeddings, pending_documents, total_documents, vectorstore
        if not pending_documents:
            return

        if HuggingFaceEmbeddings is None or FAISS is None:
            raise RuntimeError("Embedding dependencies are not installed.")

        if embeddings is None:
            embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

        batch = pending_documents
        pending_documents = []

        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            vectorstore.add_documents(batch)

        total_documents += len(batch)
        print(f"Embedded {total_documents} chunk(s) so far...")
        if return_data and all_documents is not None:
            all_documents.extend(batch)

    # ============ FILE PROCESSING PHASE ============
    process_start_time = time.time()
    
    print(f"\nScanning repository: {repo_path} (repo_name: {repo_name})")

    ordered_files = sorted(list_repo_files(repo_path, EXTENSIONS), key=lambda path: _file_priority(path, repo_path))

    processed_files = 0
    total_files = len(ordered_files)

    def merge_processed_file(result: Dict[str, Any]):
        nonlocal processed_files
        prefixed_rel_path = result.get("prefixed_rel_path")
        if not prefixed_rel_path:
            return
        processed_files += 1

        symbol_table = result.get("symbol_table")
        if symbol_table is not None:
            symbol_resolver.add_symbol_table(prefixed_rel_path, symbol_table)
            if verbose:
                print(f"Extracted {len(symbol_table.all_symbols)} symbols from {prefixed_rel_path}")

        dataflow_analysis = result.get("dataflow_analysis")
        if dataflow_analysis:
            dataflow_by_file[prefixed_rel_path] = dataflow_analysis
            if verbose:
                print(f"Data flow analysis for {len(dataflow_analysis)} functions in {prefixed_rel_path}")

        async_analysis = result.get("async_analysis")
        if async_analysis:
            async_patterns_by_file[prefixed_rel_path] = async_analysis
            if verbose:
                print(
                    f"Async pattern analysis found {async_analysis.get('pattern_count', 0)} pattern(s) in {prefixed_rel_path}"
                )

        for caller_name, callee_symbol in result.get("raw_calls", []):
            raw_call_records.append((prefixed_rel_path, caller_name, callee_symbol))

        for chunk in result.get("chunks", []):
            name = chunk.get("name")
            node_type = chunk.get("node_type") or ""
            if name and any(token in str(node_type).lower() for token in ("function", "method", "class")):
                symbol_to_fqn.setdefault(name, []).append(f"{prefixed_rel_path}:{name}")

        pending_documents.extend(result.get("documents", []))
        if len(pending_documents) >= EMBED_BATCH_SIZE:
            flush_document_batch()

        if verbose:
            print(
                f"Processed {result['file_path']} using {result.get('used_parser', 'unknown')} "
                f"({len(result.get('chunks', []))} chunks)"
            )
        elif processed_files % PROGRESS_LOG_EVERY == 0 or processed_files == total_files:
            print(
                f"Processed {processed_files}/{total_files} file(s); "
                f"queued {len(pending_documents)} chunk(s) for embedding."
            )

    with ThreadPoolExecutor(max_workers=FILE_WORKERS) as executor:
        futures = {}
        file_iter = iter(ordered_files)

        def submit_more():
            while len(futures) < MAX_IN_FLIGHT_FILES:
                try:
                    next_file = next(file_iter)
                except StopIteration:
                    break
                future = executor.submit(
                    _process_repo_file,
                    next_file,
                    repo_path,
                    repo_name,
                    repo_commit_sha,
                    repo_commit_msg,
                    repo_commit_date,
                )
                futures[future] = next_file

        submit_more()
        while futures:
            for _, future in _drain_completed_futures(futures, max_items=1):
                try:
                    result = future.result()
                except Exception as exc:
                    print(f"Skipped worker result due to error: {exc}")
                    submit_more()
                    continue

                if not result.get("skip"):
                    merge_processed_file(result)
                if GC_COLLECT_EVERY and processed_files and processed_files % GC_COLLECT_EVERY == 0:
                    gc.collect()
                submit_more()

    flush_document_batch()
    
    process_duration = time.time() - process_start_time

    print(f"Loaded {total_documents} chunks total from {repo_path}")
    print(f"Indexed {len(symbol_resolver.symbol_tables)} files with symbol tables")

    if total_documents == 0:
        print("No documents to embed; aborting ingestion.")
        # Cleanup if used ZIP/API
        if zip_cleanup_root and 'cleanup_zip_extraction' in dir():
            from .zip_ingestion import cleanup_zip_extraction
            cleanup_zip_extraction(None, zip_cleanup_root)
        if return_data:
            return {
                "documents": [],
                "call_graph": {},
                "symbol_resolver": symbol_resolver,
                "dataflow_by_file": {},
                "async_patterns_by_file": {},
                "kg_builder": kg_builder,
                "boot_chain": {},
                "repo_name": repo_name,
            }
        return

    for rel_path, caller_name, callee_symbol in raw_call_records:
        caller_fqn = f"{rel_path}:{caller_name}"
        candidates = symbol_to_fqn.get(callee_symbol) or []
        callee_fqn = candidates[0] if candidates else callee_symbol
        call_graph.setdefault(caller_fqn, set()).add(callee_fqn)

    symbol_metadata = _build_symbol_metadata(symbol_resolver)
    boot_chain = _build_boot_chain(call_graph, symbol_metadata, repo_name)

    print("\nBuilding comprehensive knowledge graph...")
    kg_builder.build_from_symbols(symbol_resolver.symbol_tables)
    print("Added symbol nodes to knowledge graph")

    call_graph_for_kg = {caller: list(callees) for caller, callees in call_graph.items()}
    kg_builder.build_from_dataflow(dataflow_by_file, call_graph_for_kg)
    print("Added data flow edges to knowledge graph")
    kg_builder.add_call_graph(call_graph_for_kg)
    print("Added call graph edges to knowledge graph")
    core_structures = _build_core_structures(symbol_resolver, kg_builder, repo_name)

    print("\nKnowledge Graph Statistics:")
    print(f"   Nodes: {len(kg_builder.graph.nodes)}")
    print(f"   Edges: {len(kg_builder.graph.edges)}")

    edge_types = {}
    for edge in kg_builder.graph.edges:
        edge_types[edge.edge_type] = edge_types.get(edge.edge_type, 0) + 1

    print("   Edge types:")
    for edge_type, count in sorted(edge_types.items()):
        print(f"      {edge_type}: {count}")

    contributions_data = {}
    
    # For GitHub repos: always extract contributions via API (fast, no git needed)
    if owner and repo and extract_contributions_via_api:
        print("\nExtracting contributions via GitHub API...")
        try:
            contributions_data = extract_contributions_via_api(
                owner, repo, github_token,
                branch=default_branch,
            )
            if contributions_data:
                save_contributions(repo_name, contributions_data)
                total_authors = contributions_data.get("total_authors", 0)
                print(f"Extracted contributions from {total_authors} author(s) via GitHub API")
            else:
                print("No contribution data returned from GitHub API")
        except Exception as exc:
            print(f"GitHub API contribution extraction failed: {exc}")
    
    # Fallback: git-based extraction for local repos (if enabled and no API data yet)
    if not contributions_data and extract_contributions and analyze_contributions:
        print("\nAnalyzing code contributions from local git history...")
        try:
            contributions_data = extract_contributions(
                repo_path,
                max_commits=contribution_commit_limit or None,
                include_commit_details=CONTRIBUTION_INCLUDE_DETAILS,
            )
            print(f"Extracted contributions from {contributions_data.get('total_authors', 0)} authors")
        except Exception as exc:
            print(f"Failed to extract contributions: {exc}")

    if return_data:
        # Cleanup ZIP/API temp files if used
        if zip_cleanup_root:
            try:
                from .zip_ingestion import cleanup_zip_extraction
                cleanup_zip_extraction(None, zip_cleanup_root)
            except Exception as e:
                print(f"Warning: Failed to cleanup temp files: {e}")
        
        return {
            "documents": all_documents or [],
            "call_graph": call_graph,
            "symbol_resolver": symbol_resolver,
            "dataflow_by_file": dataflow_by_file,
            "async_patterns_by_file": async_patterns_by_file,
            "kg_builder": kg_builder,
            "vectorstore": vectorstore,
            "contributions": contributions_data,
            "boot_chain": boot_chain,
            "core_structures": core_structures,
            "repo_name": repo_name,
            "ingestion_stats": {
                "method": ingestion_method,
                "total_duration": time.time() - overall_start_time,
                "load_duration": load_duration,
                "process_duration": process_duration,
            }
        }

    os.makedirs(paths["data_dir"], exist_ok=True)

    call_graph_serializable = {caller: list(callees) for caller, callees in call_graph.items()}
    with open(paths["callgraph_path"], "w", encoding="utf-8") as handle:
        json.dump(call_graph_serializable, handle, indent=2, ensure_ascii=False)
    print(f"Saved call graph to `{paths['callgraph_path']}` with {len(call_graph_serializable)} caller nodes.")

    with open(paths["bootchain_path"], "w", encoding="utf-8") as handle:
        json.dump(boot_chain, handle, indent=2, ensure_ascii=False)
    print(f"Saved boot chain to `{paths['bootchain_path']}` with {len(boot_chain.get('ordered_steps', []))} ordered step(s).")

    with open(paths["corestructures_path"], "w", encoding="utf-8") as handle:
        json.dump(core_structures, handle, indent=2, ensure_ascii=False)
    print(f"Saved core structures to `{paths['corestructures_path']}` with {len(core_structures.get('structures', []))} ranked structure(s).")

    symbol_resolver.build_cross_references()
    symbol_table_path = os.path.join(paths["data_dir"], "symbol_table.json")
    symbol_data = {
        "global_index": symbol_resolver.export_cross_reference_graph(),
        "file_symbols": {
            file_path: symbol_table.export_to_dict()
            for file_path, symbol_table in symbol_resolver.symbol_tables.items()
        },
    }
    with open(symbol_table_path, "w", encoding="utf-8") as handle:
        json.dump(symbol_data, handle, indent=2, ensure_ascii=False)
    print(
        f"Saved symbol table to `{symbol_table_path}` with "
        f"{sum(len(st.all_symbols) for st in symbol_resolver.symbol_tables.values())} total symbols."
    )

    dataflow_path = os.path.join(paths["data_dir"], "dataflow_analysis.json")
    with open(dataflow_path, "w", encoding="utf-8") as handle:
        json.dump(dataflow_by_file, handle, indent=2, ensure_ascii=False)

    total_functions_analyzed = sum(len(funcs) for funcs in dataflow_by_file.values())
    print(f"Saved data flow analysis for {total_functions_analyzed} functions to `{dataflow_path}`")

    total_def_use_chains = sum(
        len(func_analysis.get("def_use_chains", {}))
        for file_funcs in dataflow_by_file.values()
        for func_analysis in file_funcs.values()
    )
    print(f"Tracked {total_def_use_chains} definition-use chains across all functions")

    async_patterns_path = os.path.join(paths["data_dir"], "async_patterns.json")
    with open(async_patterns_path, "w", encoding="utf-8") as handle:
        json.dump(async_patterns_by_file, handle, indent=2, ensure_ascii=False)
    total_async_patterns = sum(
        entry.get("pattern_count", 0)
        for entry in async_patterns_by_file.values()
        if isinstance(entry, dict)
    )
    print(f"Saved async pattern analysis with {total_async_patterns} pattern(s) to `{async_patterns_path}`")

    kg_path = os.path.join(paths["data_dir"], "knowledge_graph.json")
    kg_builder.export(kg_path)

    if contributions_data:
        contributions_path = os.path.join(paths["data_dir"], "contributions.json")
        with open(contributions_path, "w", encoding="utf-8") as handle:
            json.dump(contributions_data, handle, indent=2, ensure_ascii=False, default=str)
        print(f"Saved contributions data to `{contributions_path}`")

    os.makedirs(paths["vector_dir"], exist_ok=True)
    vectorstore.save_local(paths["vector_dir"])
    print(f"Saved FAISS vector store to `{paths['vector_dir']}`")
    
    # ============ PRINT TIMING SUMMARY ============
    total_duration = time.time() - overall_start_time
    
    print("\n" + "=" * 70)
    print("INGESTION COMPLETE - TIMING SUMMARY")
    print("=" * 70)
    print(f"Ingestion Method:     {ingestion_method}")
    print(f"Repository:           {repo_name}")
    print(f"Total Files Indexed:  {len(symbol_resolver.symbol_tables)}")
    print(f"Total Chunks Created: {total_documents}")
    print()
    print(f"Timeline:")
    print(f"  [1] Repository Loading: {_format_duration(load_duration)}")
    print(f"  [2] File Processing:    {_format_duration(process_duration)}")
    print(f"  [3] Total Duration:     {_format_duration(total_duration)}")
    print("=" * 70)
    
    # ============ SAVE EVALUATION METRICS ============
    if save_ingestion_metrics:
        try:
            # Calculate total unique nodes in call graph
            callers = set(call_graph.keys())
            callees = set()
            for callee_set in call_graph.values():
                callees.update(callee_set)
            total_nodes_cg = len(callers | callees)
            
            save_ingestion_metrics(
                repo_name=repo_name,
                ingestion_method=ingestion_method,
                load_duration=load_duration,
                process_duration=process_duration,
                total_duration=total_duration,
                total_files=total_nodes_cg,
                processed_files=len(symbol_resolver.symbol_tables),
                total_documents=total_documents,
                symbol_resolver=symbol_resolver,
                kg_builder=kg_builder,
                vectorstore=vectorstore,
                call_graph=call_graph,
                embed_model=EMBED_MODEL,
            )
        except Exception as e:
            print(f"[Evaluation] Warning: Failed to save ingestion metrics: {e}")
    
    # ============ SAVE CONTRIBUTION METRICS ============
    if save_contribution_metrics and contributions_data:
        try:
            # Aggregate lines and files from all authors
            total_lines_added = 0
            total_lines_deleted = 0
            total_files_changed = 0
            authors_dict = contributions_data.get("authors", {})
            
            for author_data in authors_dict.values():
                total_lines_added += author_data.get("lines_added", 0)
                total_lines_deleted += author_data.get("lines_deleted", 0)
                total_files_changed += author_data.get("files_changed", 0)
            
            # Calculate top contributor share
            total_authors = contributions_data.get("total_authors", 0)
            max_commits_one_author = 0
            if authors_dict:
                max_commits_one_author = max(
                    author_data.get("commits", 0) for author_data in authors_dict.values()
                )
            total_commits = contributions_data.get("total_commits", 0)
            top_contributor_share = (max_commits_one_author / max(total_commits, 1)) * 100
            
            # Get analysis scope flags
            analysis_scope = contributions_data.get("analysis_scope", {})
            
            save_contribution_metrics(
                repo_name=repo_name,
                repo_path=repo_path,
                total_authors=total_authors,
                total_commits=total_commits,
                total_lines_added=total_lines_added,
                total_lines_deleted=total_lines_deleted,
                total_files_changed=total_files_changed,
                top_contributor_share_pct=top_contributor_share,
                commit_sample_size=analysis_scope.get("commit_sample_size", analysis_scope.get("processed_commits", 0)),
                detail_commit_sample_size=analysis_scope.get("detail_commit_sample_size", 0),
                fallback_mode=analysis_scope.get("fallback_mode", False),
                timed_out=analysis_scope.get("timed_out", False),
                has_line_stats=total_lines_added > 0 or total_lines_deleted > 0,
                has_file_stats=total_files_changed > 0,
            )
        except Exception as e:
            print(f"[Evaluation] Warning: Failed to save contribution metrics: {e}")
    
    # ============ SAVE GRAPH METRICS ============
    if save_graph_metrics:
        try:
            save_graph_metrics(
                repo_name=repo_name,
                call_graph=call_graph,
                kg_builder=kg_builder,
                symbol_resolver=symbol_resolver,
            )
        except Exception as e:
            print(f"[Evaluation] Warning: Failed to save graph metrics: {e}")
    
    
    # Cleanup temporary files if API/ZIP ingestion was used
    if zip_cleanup_root and os.path.exists(zip_cleanup_root):
        try:
            import shutil
            shutil.rmtree(zip_cleanup_root, ignore_errors=True)
        except Exception as e:
            print(f"Warning: Failed to cleanup temp files: {e}")


def ingest_repos(
    repo_list: list,
    aggregate: bool = True,
    analyze_contributions: Optional[bool] = None,
    contribution_commit_limit: Optional[int] = None,
    verbose: bool = False,
):
    """Ingest multiple repositories and optionally aggregate the results."""
    all_documents = []
    all_call_graphs = {}
    all_symbol_resolvers = []
    all_dataflow = {}
    all_kg_builders = []
    all_contributions = {}
    all_boot_chains = {}
    all_core_structures = {}
    all_async_patterns = {}
    repo_names = []

    for index, repo_item in enumerate(repo_list):
        if isinstance(repo_item, tuple):
            repo_url_or_path, repo_name = repo_item
        else:
            repo_url_or_path = repo_item
            repo_name = None

        print(f"\n{'=' * 60}")
        print(f"Processing repository {index + 1}/{len(repo_list)}: {repo_url_or_path}")
        print(f"{'=' * 60}\n")

        result = ingest_repo(
            repo_url_or_path,
            repo_name=repo_name,
            return_data=True,
            analyze_contributions=analyze_contributions,
            contribution_commit_limit=contribution_commit_limit,
            verbose=verbose,
        )
        if result:
            all_documents.extend(result["documents"])
            all_call_graphs.update(result["call_graph"])
            all_symbol_resolvers.append(result["symbol_resolver"])
            all_dataflow.update(result["dataflow_by_file"])
            all_kg_builders.append(result["kg_builder"])
            if result.get("contributions"):
                all_contributions[result["repo_name"]] = result["contributions"]
            if result.get("boot_chain"):
                all_boot_chains[result["repo_name"]] = result["boot_chain"]
            if result.get("core_structures"):
                all_core_structures[result["repo_name"]] = result["core_structures"]
            if result.get("async_patterns_by_file"):
                all_async_patterns[result["repo_name"]] = result["async_patterns_by_file"]
            repo_names.append(result["repo_name"])

    if not aggregate:
        print("\nAll repositories processed separately.")
        return {
            "repos": repo_names,
            "per_repo_data": [
                {
                    "repo_name": name,
                    "documents_count": len([doc for doc in all_documents if doc.metadata.get("repo_name") == name]),
                }
                for name in repo_names
            ],
        }

    print(f"\n{'=' * 60}")
    print(f"Aggregating data from {len(repo_list)} repositories...")
    print(f"{'=' * 60}\n")

    aggregated_symbol_resolver = SymbolResolver()
    for resolver in all_symbol_resolvers:
        for file_path, symbol_table in resolver.symbol_tables.items():
            aggregated_symbol_resolver.add_symbol_table(file_path, symbol_table)
    aggregated_symbol_resolver.build_cross_references()

    aggregated_kg = KnowledgeGraphBuilder()
    for kg_builder in all_kg_builders:
        for node in kg_builder.graph.nodes.values():
            aggregated_kg.graph.add_node(node)
        for edge in kg_builder.graph.edges:
            aggregated_kg.graph.add_edge(edge)

    print("Merging vector stores...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    merged_vectorstore = FAISS.from_documents(all_documents, embeddings)

    aggregated_paths = _get_repo_paths(None)
    os.makedirs(aggregated_paths["data_dir"], exist_ok=True)

    with open(aggregated_paths["callgraph_path"], "w", encoding="utf-8") as handle:
        json.dump({caller: list(callees) for caller, callees in all_call_graphs.items()}, handle, indent=2, ensure_ascii=False)
    print(f"Saved aggregated call graph with {len(all_call_graphs)} caller nodes.")

    aggregated_boot_chain = {
        "repo_name": "aggregated",
        "repositories": all_boot_chains,
        "summary": f"Boot chain data preserved for {len(all_boot_chains)} repository/repositories.",
    }
    with open(aggregated_paths["bootchain_path"], "w", encoding="utf-8") as handle:
        json.dump(aggregated_boot_chain, handle, indent=2, ensure_ascii=False)
    print(f"Saved aggregated boot chain metadata for {len(all_boot_chains)} repositories.")

    aggregated_core_structures = {
        "repo_name": "aggregated",
        "repositories": all_core_structures,
        "summary": f"Core structure data preserved for {len(all_core_structures)} repository/repositories.",
    }
    with open(aggregated_paths["corestructures_path"], "w", encoding="utf-8") as handle:
        json.dump(aggregated_core_structures, handle, indent=2, ensure_ascii=False)
    print(f"Saved aggregated core-structure metadata for {len(all_core_structures)} repositories.")

    symbol_table_path = os.path.join(aggregated_paths["data_dir"], "symbol_table.json")
    symbol_data = {
        "global_index": aggregated_symbol_resolver.export_cross_reference_graph(),
        "file_symbols": {
            file_path: symbol_table.export_to_dict()
            for file_path, symbol_table in aggregated_symbol_resolver.symbol_tables.items()
        },
    }
    with open(symbol_table_path, "w", encoding="utf-8") as handle:
        json.dump(symbol_data, handle, indent=2, ensure_ascii=False)
    print(
        f"Saved aggregated symbol table with "
        f"{sum(len(st.all_symbols) for st in aggregated_symbol_resolver.symbol_tables.values())} total symbols."
    )

    dataflow_path = os.path.join(aggregated_paths["data_dir"], "dataflow_analysis.json")
    with open(dataflow_path, "w", encoding="utf-8") as handle:
        json.dump(all_dataflow, handle, indent=2, ensure_ascii=False)
    print("Saved aggregated data flow analysis.")

    async_patterns_path = os.path.join(aggregated_paths["data_dir"], "async_patterns.json")
    with open(async_patterns_path, "w", encoding="utf-8") as handle:
        json.dump(all_async_patterns, handle, indent=2, ensure_ascii=False)
    print("Saved aggregated async pattern analysis.")

    kg_path = os.path.join(aggregated_paths["data_dir"], "knowledge_graph.json")
    aggregated_kg.export(kg_path)
    print(f"Saved aggregated knowledge graph with {len(aggregated_kg.graph.nodes)} nodes and {len(aggregated_kg.graph.edges)} edges.")

    if all_contributions:
        contributions_path = os.path.join(aggregated_paths["data_dir"], "contributions.json")
        with open(contributions_path, "w", encoding="utf-8") as handle:
            json.dump(all_contributions, handle, indent=2, ensure_ascii=False, default=str)
        print(f"Saved aggregated contributions data from {len(all_contributions)} repositories.")

    os.makedirs(aggregated_paths["vector_dir"], exist_ok=True)
    merged_vectorstore.save_local(aggregated_paths["vector_dir"])

    print(f"\nSuccessfully aggregated {len(repo_list)} repositories.")
    return {
        "repos": repo_names,
        "total_documents": len(all_documents),
        "total_call_graph_nodes": len(all_call_graphs),
        "total_symbols": sum(len(st.all_symbols) for st in aggregated_symbol_resolver.symbol_tables.values()),
        "kg_nodes": len(aggregated_kg.graph.nodes),
        "kg_edges": len(aggregated_kg.graph.edges),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        repos = sys.argv[1:]
        print(f"Processing {len(repos)} repositories...")
        ingest_repos(repos, aggregate=True)
        print(f"\nCompleted! Processed {len(repos)} repositories.")
    else:
        repo_url = input("Enter GitHub repo URL or local path: ").strip()
        ingest_repo(repo_url)