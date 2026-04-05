import hashlib
import json
import os
import shutil
from abc import ABC, abstractmethod
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .github_loader import (
    GitHubAPIError,
    get_commit_details,
    get_file_content,
    get_repo_metadata,
    get_repo_tree,
)
from redis_storage import delete_keys, get_json, get_json_by_key, list_keys, save_json, save_json_key
from .github_contributions import extract_contributions_via_api, save_contributions
from .ingest import (
    EMBED_BATCH_SIZE,
    EMBED_MODEL,
    EXTENSIONS,
    FILE_WORKERS,
    MAX_IN_FLIGHT_FILES,
    PROGRESS_LOG_EVERY,
    _build_boot_chain,
    _build_core_structures,
    _build_symbol_name_lookup,
    _build_symbol_metadata,
    _get_repo_paths,
    _process_repo_file,
    _resolve_call_graph_symbol_fqn,
)
from .knowledge_graph import KnowledgeGraphBuilder
from .resolver import SymbolResolver
from .symbols import Scope, Symbol, SymbolTable, TypeInfo
from .utils import GENERATED_MARKERS, MAX_FILE_BYTES, SKIP_DIR_NAMES, SKIP_FILE_NAMES, SKIP_SUFFIXES

try:
    from langchain_community.embeddings import JinaEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
except ImportError:
    JinaEmbeddings = None
    FAISS = None
    Document = None


REPO_INDEX_METADATA = "repo_index_metadata.json"
API_ARTIFACT_DIR = "api_artifacts"
API_SOURCE_DIR = "api_source"


class RepoSource(ABC):
    """Abstract file source for ingestion."""

    @abstractmethod
    def list_files(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_file_content(self, path: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_file_sha(self, path: str) -> Optional[str]:
        raise NotImplementedError


class GitRepoSource(RepoSource):
    """Placeholder wrapper around local filesystem repositories."""

    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)

    def list_files(self) -> List[Dict[str, Any]]:
        file_entries: List[Dict[str, Any]] = []
        for root, _, files in os.walk(self.repo_root):
            for file_name in files:
                rel_path = os.path.relpath(os.path.join(root, file_name), self.repo_root).replace("\\", "/")
                file_entries.append({"path": rel_path, "sha": None, "size": os.path.getsize(os.path.join(root, file_name))})
        return file_entries

    def get_file_content(self, path: str) -> str:
        full_path = os.path.join(self.repo_root, path.replace("/", os.sep))
        with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()

    def get_file_sha(self, path: str) -> Optional[str]:
        return None


class GitHubAPISource(RepoSource):
    """Repository source backed by GitHub REST APIs."""

    def __init__(self, repo_url: str, branch: Optional[str] = None, token: Optional[str] = None):
        self.repo_url = repo_url
        self.owner, self.repo = parse_github_repo_url(repo_url)
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.session = requests.Session()
        repo_meta = get_repo_metadata(self.owner, self.repo, token=self.token)
        self.branch = branch or repo_meta.get("default_branch") or "main"
        self._tree_cache: Optional[List[Dict[str, Any]]] = None
        self._tree_index: Dict[str, Dict[str, Any]] = {}

    def list_files(self) -> List[Dict[str, Any]]:
        if self._tree_cache is None:
            self._tree_cache = get_repo_tree(
                self.owner,
                self.repo,
                self.branch,
                token=self.token,
                session=self.session,
            )
            self._tree_index = {entry["path"]: entry for entry in self._tree_cache if entry.get("path")}
        return list(self._tree_cache)

    def get_file_content(self, path: str) -> str:
        return get_file_content(
            self.owner,
            self.repo,
            path,
            self.branch,
            token=self.token,
            session=self.session,
        )

    def get_file_sha(self, path: str) -> Optional[str]:
        if not self._tree_index:
            self.list_files()
        entry = self._tree_index.get(path)
        return entry.get("sha") if entry else None

    def get_head_commit(self) -> Dict[str, Optional[str]]:
        return get_commit_details(
            self.owner,
            self.repo,
            self.branch,
            token=self.token,
            session=self.session,
        )


def parse_github_repo_url(repo_url: str) -> Tuple[str, str]:
    if repo_url.startswith("git@github.com:"):
        cleaned = repo_url.split("git@github.com:", 1)[1]
        cleaned = cleaned[:-4] if cleaned.endswith(".git") else cleaned
        owner, repo = cleaned.split("/", 1)
        return owner, repo

    parsed = urlparse(repo_url)
    if "github.com" not in parsed.netloc:
        raise ValueError(f"Unsupported GitHub URL: {repo_url}")

    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"Could not parse owner/repo from URL: {repo_url}")

    owner = path_parts[0]
    repo = path_parts[1][:-4] if path_parts[1].endswith(".git") else path_parts[1]
    return owner, repo


def _metadata_path(repo_name: str) -> str:
    return os.path.join(_get_repo_paths(repo_name)["data_dir"], REPO_INDEX_METADATA)


def _artifact_dir(repo_name: str) -> str:
    return os.path.join(_get_repo_paths(repo_name)["data_dir"], API_ARTIFACT_DIR)


def _source_dir(repo_name: str) -> str:
    return os.path.join(_get_repo_paths(repo_name)["data_dir"], API_SOURCE_DIR)


def _artifact_path(repo_name: str, rel_path: str) -> str:
    digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()
    return os.path.join(_artifact_dir(repo_name), f"{digest}.json")


def _load_metadata(repo_name: str) -> Dict[str, Any]:
    return get_json(repo_name, "metadata") or {}


def _load_existing_contributions(repo_name: str) -> Optional[Dict[str, Any]]:
    return get_json(repo_name, "contributions")


def _save_metadata(repo_name: str, payload: Dict[str, Any]) -> None:
    save_json(repo_name, "metadata", payload)


def _path_is_supported(rel_path: str, size: Optional[int] = None) -> bool:
    rel_lower = rel_path.lower()
    parts = set(rel_lower.split("/"))
    base_name = os.path.basename(rel_lower)

    if not rel_lower.endswith(tuple(ext.lower() for ext in EXTENSIONS)):
        return False
    if parts & {name.lower() for name in SKIP_DIR_NAMES}:
        return False
    if base_name in {name.lower() for name in SKIP_FILE_NAMES}:
        return False
    if any(rel_lower.endswith(suffix) for suffix in SKIP_SUFFIXES):
        return False
    if size is not None and size > MAX_FILE_BYTES:
        return False
    return True


def _looks_generated_text(content: str) -> bool:
    header = content[:2048].lower()
    return any(marker in header for marker in GENERATED_MARKERS)


def _virtual_file_priority(entry: Dict[str, Any]) -> Tuple[int, int, str]:
    rel_path = entry.get("path", "").lower()
    base_name = os.path.basename(rel_path)
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
    return (priority, int(entry.get("size") or 0), rel_path)


def _write_snapshot_file(repo_name: str, rel_path: str, content: str) -> str:
    snapshot_root = _source_dir(repo_name)
    destination = os.path.join(snapshot_root, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "w", encoding="utf-8", errors="ignore") as handle:
        handle.write(content)
    return destination


def _serialize_processed_result(result: Dict[str, Any], rel_path: str, sha: Optional[str]) -> Dict[str, Any]:
    symbol_table = result.get("symbol_table")
    return {
        "relative_path": rel_path,
        "sha": sha,
        "result": {
            "prefixed_rel_path": result.get("prefixed_rel_path"),
            "chunks": result.get("chunks", []),
            "documents": [
                {
                    "page_content": document.page_content,
                    "metadata": document.metadata,
                }
                for document in result.get("documents", [])
            ],
            "symbol_table": symbol_table.export_to_dict() if symbol_table is not None else None,
            "dataflow_analysis": result.get("dataflow_analysis"),
            "async_analysis": result.get("async_analysis"),
            "raw_calls": result.get("raw_calls", []),
            "used_parser": result.get("used_parser"),
        },
    }


def _deserialize_symbol_table(payload: Optional[Dict[str, Any]]) -> Optional[SymbolTable]:
    if not payload:
        return None

    file_path = payload.get("file_path")
    symbol_table = SymbolTable(file_path)
    symbol_table.scopes = {}
    symbol_table.all_symbols = {}
    symbol_table.current_scope_stack = [f"{file_path}:global"]
    symbol_table.imports = {}

    for scope_id, scope_data in payload.get("scopes", {}).items():
        scope = Scope(
            scope_id=scope_id,
            scope_type=scope_data.get("scope_type", "global"),
            parent_scope_id=scope_data.get("parent_scope_id"),
            file_path=file_path,
            class_name=scope_data.get("class_name"),
            imports=scope_data.get("imports", {}),
            mro=scope_data.get("mro", []),
        )
        symbol_table.scopes[scope_id] = scope
        symbol_table.imports.update(scope.imports)

    for fqn, symbol_data in payload.get("symbols", {}).items():
        type_hint = symbol_data.get("type_hint")
        symbol = Symbol(
            name=symbol_data.get("name"),
            kind=symbol_data.get("kind"),
            scope_id=symbol_data.get("scope_id"),
            line_number=int(symbol_data.get("line", 0)),
            end_line=int(symbol_data.get("end_line", symbol_data.get("line", 0))),
            file_path=file_path,
            type_hint=TypeInfo(type_hint) if type_hint else None,
            is_static=bool(symbol_data.get("is_static")),
            is_private=bool(symbol_data.get("is_private")),
            docstring=symbol_data.get("docstring"),
            parent_symbol=symbol_data.get("parent_symbol"),
        )
        symbol_table.all_symbols[fqn] = symbol
        scope = symbol_table.scopes.get(symbol.scope_id)
        if scope:
            scope.symbols[symbol.name] = symbol

    if f"{file_path}:global" not in symbol_table.scopes:
        symbol_table.scopes[f"{file_path}:global"] = Scope(
            scope_id=f"{file_path}:global",
            scope_type="global",
            file_path=file_path,
        )

    return symbol_table


def _deserialize_processed_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = payload.get("result", {})
    return {
        "prefixed_rel_path": result.get("prefixed_rel_path"),
        "chunks": result.get("chunks", []),
        "documents": [
            Document(page_content=document["page_content"], metadata=document.get("metadata", {}))
            for document in result.get("documents", [])
        ],
        "symbol_table": _deserialize_symbol_table(result.get("symbol_table")),
        "dataflow_analysis": result.get("dataflow_analysis"),
        "async_analysis": result.get("async_analysis"),
        "raw_calls": [tuple(entry) for entry in result.get("raw_calls", [])],
        "used_parser": result.get("used_parser", "unknown"),
        "file_path": payload.get("relative_path"),
    }


def _persist_artifact(repo_name: str, rel_path: str, sha: Optional[str], result: Dict[str, Any]) -> None:
    payload = _serialize_processed_result(result, rel_path, sha)
    digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()
    save_json_key(f"repo:{repo_name}:api_artifact:{digest}", payload)


def _load_all_artifacts(repo_name: str) -> List[Dict[str, Any]]:
    artifact_keys = sorted(list_keys(f"repo:{repo_name}:api_artifact:*"))
    results: List[Dict[str, Any]] = []
    for key in artifact_keys:
        payload = get_json_by_key(key)
        if payload is None:
            continue
        results.append(_deserialize_processed_result(payload))
    return results


def _remove_cached_file(repo_name: str, rel_path: str) -> None:
    digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()
    delete_keys(f"repo:{repo_name}:api_artifact:{digest}")

    source_path = os.path.join(_source_dir(repo_name), rel_path.replace("/", os.sep))
    if os.path.exists(source_path):
        os.remove(source_path)


def _materialize_outputs(
    repo_name: str,
    processed_results: Iterable[Dict[str, Any]],
    repo_commit_sha: str,
    repo_commit_msg: str,
    repo_commit_date: Optional[str],
    return_data: bool = False,
) -> Optional[Dict[str, Any]]:
    paths = _get_repo_paths(repo_name)
    all_documents = [] if return_data else None
    pending_documents: List[Document] = []
    raw_call_records: List[Tuple[str, str, str]] = []

    symbol_resolver = SymbolResolver()
    dataflow_by_file: Dict[str, Dict[str, Any]] = {}
    async_patterns_by_file: Dict[str, Dict[str, Any]] = {}
    kg_builder = KnowledgeGraphBuilder()
    call_graph: Dict[str, set] = {}

    embeddings = None
    vectorstore = None
    total_documents = 0

    def flush_document_batch() -> None:
        nonlocal embeddings, pending_documents, total_documents, vectorstore
        if not pending_documents:
            return
        if JinaEmbeddings is None or FAISS is None:
            raise RuntimeError("Embedding dependencies are not installed.")
        if embeddings is None:
            embeddings = JinaEmbeddings(jina_api_key=os.getenv("JINA_API_KEY"), model_name=EMBED_MODEL)

        batch = pending_documents
        pending_documents = []
        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            vectorstore.add_documents(batch)
        total_documents += len(batch)
        if return_data and all_documents is not None:
            all_documents.extend(batch)

    processed_count = 0
    result_list = list(processed_results)
    total_results = len(result_list)
    for result in result_list:
        prefixed_rel_path = result.get("prefixed_rel_path")
        if not prefixed_rel_path:
            continue
        processed_count += 1

        symbol_table = result.get("symbol_table")
        if symbol_table is not None:
            symbol_resolver.add_symbol_table(prefixed_rel_path, symbol_table)

        dataflow_analysis = result.get("dataflow_analysis")
        if dataflow_analysis:
            dataflow_by_file[prefixed_rel_path] = dataflow_analysis

        async_analysis = result.get("async_analysis")
        if async_analysis:
            async_patterns_by_file[prefixed_rel_path] = async_analysis

        for caller_name, callee_symbol in result.get("raw_calls", []):
            raw_call_records.append((prefixed_rel_path, caller_name, callee_symbol))

        pending_documents.extend(result.get("documents", []))
        if len(pending_documents) >= EMBED_BATCH_SIZE:
            flush_document_batch()

        if processed_count % PROGRESS_LOG_EVERY == 0 or processed_count == total_results:
            print(f"Materialized {processed_count}/{total_results} file artifact(s).")

    flush_document_batch()

    if total_documents == 0:
        print("No documents to embed; aborting API ingestion.")
        return None

    symbol_lookup = _build_symbol_name_lookup(symbol_resolver)

    for rel_path, caller_name, callee_symbol in raw_call_records:
        caller_fqn = _resolve_call_graph_symbol_fqn(symbol_lookup, rel_path, caller_name)
        callee_fqn = _resolve_call_graph_symbol_fqn(symbol_lookup, rel_path, callee_symbol)
        if caller_fqn and callee_fqn:
            call_graph.setdefault(caller_fqn, set()).add(callee_fqn)

    symbol_metadata = _build_symbol_metadata(symbol_resolver)
    boot_chain = _build_boot_chain(call_graph, symbol_metadata, repo_name)

    kg_builder.build_from_symbols(symbol_resolver.symbol_tables)
    call_graph_for_kg = {caller: list(callees) for caller, callees in call_graph.items()}
    kg_builder.build_from_dataflow(dataflow_by_file, call_graph_for_kg)
    kg_builder.add_call_graph(call_graph_for_kg)
    core_structures = _build_core_structures(symbol_resolver, kg_builder, repo_name)

    if return_data:
        return {
            "documents": all_documents or [],
            "call_graph": call_graph,
            "symbol_resolver": symbol_resolver,
            "dataflow_by_file": dataflow_by_file,
            "async_patterns_by_file": async_patterns_by_file,
            "kg_builder": kg_builder,
            "vectorstore": vectorstore,
            "contributions": {},
            "boot_chain": boot_chain,
            "core_structures": core_structures,
            "repo_name": repo_name,
        }

    os.makedirs(paths["data_dir"], exist_ok=True)
    save_json(repo_name, "call_graph", call_graph_for_kg)
    save_json(repo_name, "boot_chain", boot_chain)
    save_json(repo_name, "core_structures", core_structures)

    symbol_resolver.build_cross_references()
    symbol_data = {
        "global_index": symbol_resolver.export_cross_reference_graph(),
        "file_symbols": {
            file_path: symbol_table.export_to_dict()
            for file_path, symbol_table in symbol_resolver.symbol_tables.items()
        },
    }
    save_json(repo_name, "symbol_table", symbol_data)

    save_json(repo_name, "dataflow_analysis", dataflow_by_file)
    save_json(repo_name, "async_patterns", async_patterns_by_file)

    kg_data = kg_builder.export()
    save_json(repo_name, "knowledge_graph", kg_data)

    os.makedirs(paths["vector_dir"], exist_ok=True)
    vectorstore.save_local(paths["vector_dir"])
    return {
        "repo_name": repo_name,
        "total_documents": total_documents,
        "commit_sha": repo_commit_sha,
        "commit_message": repo_commit_msg,
        "commit_date": repo_commit_date,
    }


def _submit_worker_batch(
    source: GitHubAPISource,
    repo_name: str,
    entries: List[Dict[str, Any]],
    repo_commit_sha: str,
    repo_commit_msg: str,
    repo_commit_date: Optional[str],
) -> List[Tuple[str, Optional[str], Dict[str, Any]]]:
    snapshot_root = _source_dir(repo_name)
    os.makedirs(snapshot_root, exist_ok=True)

    def worker(entry: Dict[str, Any]) -> Optional[Tuple[str, Optional[str], Dict[str, Any]]]:
        rel_path = entry.get("path")
        sha = entry.get("sha")
        if not rel_path:
            return None
        if not _path_is_supported(rel_path, entry.get("size")):
            return None

        try:
            content = source.get_file_content(rel_path)
        except GitHubAPIError as exc:
            print(f"Skipped {rel_path}: {exc}")
            return None

        if not content.strip() or _looks_generated_text(content):
            return None

        cached_path = _write_snapshot_file(repo_name, rel_path, content)
        processed = _process_repo_file(
            cached_path,
            snapshot_root,
            repo_name,
            repo_commit_sha,
            repo_commit_msg,
            repo_commit_date,
        )
        if processed.get("skip"):
            return None
        return rel_path, sha, processed

    futures = {}
    completed: List[Tuple[str, Optional[str], Dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=FILE_WORKERS) as executor:
        entry_iter = iter(sorted(entries, key=_virtual_file_priority))

        def submit_more() -> None:
            while len(futures) < MAX_IN_FLIGHT_FILES:
                try:
                    next_entry = next(entry_iter)
                except StopIteration:
                    break
                futures[executor.submit(worker, next_entry)] = next_entry.get("path")

        submit_more()
        while futures:
            done, _ = wait(list(futures.keys()), return_when=FIRST_COMPLETED)
            for future in done:
                rel_path = futures.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    print(f"Skipped API worker result for {rel_path}: {exc}")
                    submit_more()
                    continue
                if result is not None:
                    completed.append(result)
                    if len(completed) % PROGRESS_LOG_EVERY == 0:
                        print(f"Fetched and processed {len(completed)} API file(s)...")
                submit_more()

    return completed


def ingest_repo_via_api(
    repo_url: str,
    branch: Optional[str] = "main",
    token: Optional[str] = None,
    repo_name: Optional[str] = None,
    return_data: bool = False,
) -> Optional[Dict[str, Any]]:
    """Ingest a GitHub repository via REST APIs without cloning it."""
    source = GitHubAPISource(repo_url, branch=branch, token=token)
    repo_name = repo_name or source.repo
    paths = _get_repo_paths(repo_name)
    head_commit = source.get_head_commit()
    repo_commit_sha = head_commit.get("sha") or "unknown"
    repo_commit_msg = head_commit.get("message") or "No commit message found"
    repo_commit_date = head_commit.get("date")

    shutil.rmtree(_artifact_dir(repo_name), ignore_errors=True)
    shutil.rmtree(_source_dir(repo_name), ignore_errors=True)
    os.makedirs(paths["data_dir"], exist_ok=True)

    file_entries = source.list_files()
    if not file_entries:
        print(f"No files found in {repo_url} on branch {source.branch}")
        return None

    processed = _submit_worker_batch(
        source,
        repo_name,
        file_entries,
        repo_commit_sha,
        repo_commit_msg,
        repo_commit_date,
    )
    if not processed:
        print(f"No ingestible files found in {repo_url}")
        return None

    file_shas: Dict[str, str] = {}
    for rel_path, sha, result in processed:
        file_shas[rel_path] = sha or ""
        _persist_artifact(repo_name, rel_path, sha, result)

    materialized = _materialize_outputs(
        repo_name,
        (result for _, _, result in processed),
        repo_commit_sha,
        repo_commit_msg,
        repo_commit_date,
        return_data=return_data,
    )

    _save_metadata(
        repo_name,
        {
            "source_type": "github_api",
            "repo_url": repo_url,
            "owner": source.owner,
            "repo": source.repo,
            "branch": source.branch,
            "last_commit_sha": repo_commit_sha,
            "last_commit_message": repo_commit_msg,
            "last_commit_date": repo_commit_date,
            "file_shas": file_shas,
        },
    )

    contributions = extract_contributions_via_api(
        source.owner,
        source.repo,
        source.token,
        branch=source.branch,
        existing_data=_load_existing_contributions(repo_name),
    )
    save_contributions(repo_name, contributions)
    return materialized
