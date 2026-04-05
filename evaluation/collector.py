"""Automatic metrics collection and persistence for ingestion, retrieval, and code health."""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median

try:
    from redis_storage import save_json, get_json
except ImportError:
    save_json = None
    get_json = None


def _eval_dir(repo_name: str) -> str:
    """Get or create evaluation directory for a repo."""
    eval_root = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "evaluation",
        repo_name
    )
    os.makedirs(eval_root, exist_ok=True)
    return eval_root


def _evaluation_data_type(metric_file: str) -> str:
    return f"evaluation:{metric_file[:-5]}"


def _save_evaluation_data(repo_name: str, metric_file: str, data: dict) -> None:
    if save_json:
        try:
            save_json(repo_name, _evaluation_data_type(metric_file), data)
        except Exception:
            pass


def _load_evaluation_data(repo_name: str, metric_file: str) -> dict:
    data = None
    if get_json:
        try:
            data = get_json(repo_name, _evaluation_data_type(metric_file))
        except Exception:
            data = None
    if data is None:
        path = os.path.join(_eval_dir(repo_name), metric_file)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
            except Exception:
                data = None
    return data or {}


def _utc_now() -> str:
    """Get current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _count_repository_lines_of_code(repo_path: str) -> dict:
    """Count actual lines of code currently in the repository."""
    total_lines = 0
    total_files = 0
    lines_by_language = defaultdict(int)
    
    # Common code file extensions
    code_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".hpp",
        ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh", ".bash",
        ".css", ".scss", ".html", ".xml", ".json", ".yaml", ".yml", ".sql",
    }
    
    try:
        if not os.path.exists(repo_path):
            return {"total_lines": 0, "total_files": 0, "by_language": {}}
        
        for root, dirs, files in os.walk(repo_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'.git', '.github', 'node_modules', '__pycache__', '.pytest_cache', 'venv', '.venv', 'dist', 'build', '.next', '.nuxt'}]
            
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() in code_extensions:
                    try:
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                            total_lines += lines
                            total_files += 1
                            
                            # Categorize by language
                            lang = ext.lower().lstrip('.')
                            lines_by_language[lang] += lines
                    except Exception:
                        pass
    except Exception:
        pass
    
    return {
        "total_lines": total_lines,
        "total_files": total_files,
        "by_language": dict(lines_by_language),
    }



def save_ingestion_metrics(
    repo_name: str,
    ingestion_method: str,
    load_duration: float,
    process_duration: float,
    total_duration: float,
    total_files: int,
    processed_files: int,
    total_documents: int,
    symbol_resolver,
    kg_builder,
    vectorstore,
    call_graph,
    embed_model: str = "mixedbread-ai/mxbai-embed-large-v1",
):
    """Save ingestion run metrics. Called at end of ingest_repo()."""
    try:
        # Parser distribution from vectorstore
        parser_dist = defaultdict(int)
        if vectorstore and hasattr(vectorstore, "docstore"):
            try:
                for doc in vectorstore.docstore._dict.values():
                    parser = doc.metadata.get("parser_used", "unknown")
                    parser_dist[parser] += 1
            except Exception:
                pass
        
        # Edge type distribution from knowledge graph
        edge_types = defaultdict(int)
        if kg_builder and hasattr(kg_builder, "graph"):
            try:
                for edge in kg_builder.graph.edges:
                    edge_types[edge.edge_type] += 1
            except Exception:
                pass
        
        # Symbol metrics
        total_symbols = 0
        files_with_symbols = 0
        if symbol_resolver and hasattr(symbol_resolver, "symbol_tables"):
            files_with_symbols = len(symbol_resolver.symbol_tables)
            for symbol_table in symbol_resolver.symbol_tables.values():
                if hasattr(symbol_table, "all_symbols"):
                    total_symbols += len(symbol_table.all_symbols)
        
        coverage_pct = (files_with_symbols / max(processed_files, 1)) * 100
        avg_chunks_per_file = total_documents / max(processed_files, 1)
        
        # KG stats
        kg_nodes = 0
        kg_edges = 0
        if kg_builder and hasattr(kg_builder, "graph"):
            try:
                kg_nodes = len(kg_builder.graph.nodes)
                kg_edges = len(kg_builder.graph.edges)
            except Exception:
                pass
        
        metrics = {
            "repo_name": repo_name,
            "timestamp": _utc_now(),
            "ingestion_method": ingestion_method,
            "timing": {
                "total_seconds": round(total_duration, 2),
                "load_seconds": round(load_duration, 2),
                "process_seconds": round(process_duration, 2),
            },
            "file_metrics": {
                "total_found": total_files,
                "processed": processed_files,
                "skipped": max(0, total_files - processed_files),
            },
            "parser_distribution": dict(parser_dist) or {},
            "chunk_metrics": {
                "total_chunks": total_documents,
                "avg_per_file": round(avg_chunks_per_file, 2),
            },
            "symbol_metrics": {
                "total_symbols": total_symbols,
                "files_with_symbols": files_with_symbols,
                "coverage_pct": round(coverage_pct, 1),
            },
            "knowledge_graph": {
                "nodes": kg_nodes,
                "edges": kg_edges,
                "edge_types": dict(edge_types) or {},
            },
            "embedding_metrics": {
                "total_embedded": total_documents,
                "model": embed_model,
            },
        }
        
        dest = os.path.join(_eval_dir(repo_name), "ingestion_metrics.json")
        with open(dest, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        _save_evaluation_data(repo_name, "ingestion_metrics.json", metrics)
    except Exception as e:
        print(f"[Evaluation] Warning: Failed to save ingestion metrics: {e}")


def save_retrieval_metrics(
    repo_name: str,
    query: str,
    method: str,
    latency_seconds: float,
    docs_returned: int,
    answer: str = "",
    intent_type: str = "unknown",
    is_startup: bool = False,
    anchor_nodes: int = 0,
    total_visited: int = 0,
    max_depth: int = 0,
    edges_traversed: int = 0,
    unique_files: int = 0,
    unique_symbols: int = 0,
    unique_languages: list = None,
    answer_length_chars: int = 0,
    answer_length_words: int = 0,
    files_cited: int = 0,
    symbols_cited: int = 0,
    has_code_blocks: bool = False,
):
    """Append query metrics to retrieval_metrics.json. Recomputes aggregates."""
    try:
        if unique_languages is None:
            unique_languages = []
        
        dest = os.path.join(_eval_dir(repo_name), "retrieval_metrics.json")
        
        # Read existing
        existing = _load_evaluation_data(repo_name, "retrieval_metrics.json")
        
        queries = existing.get("queries", [])
        
        # Compute expansion ratio
        expansion_ratio = total_visited / max(anchor_nodes, 1) if anchor_nodes > 0 else 0
        
        # Append new record
        new_record = {
            "query": query,
            "answer": answer,
            "timestamp": _utc_now(),
            "method": method,
            "latency_seconds": round(latency_seconds, 2),
            "docs_returned": docs_returned,
            "intent": {
                "intent_type": intent_type,
                "is_startup": is_startup,
            },
            "graph_expansion": {
                "anchor_nodes": anchor_nodes,
                "total_visited": total_visited,
                "max_depth": max_depth,
                "edges_traversed": edges_traversed,
                "expansion_ratio": round(expansion_ratio, 2),
            },
            "diversity": {
                "unique_files": unique_files,
                "unique_symbols": unique_symbols,
                "unique_languages": unique_languages,
            },
            "answer_metrics": {
                "answer_length_chars": answer_length_chars,
                "answer_length_words": answer_length_words,
                "files_cited": files_cited,
                "symbols_cited": symbols_cited,
                "has_code_blocks": has_code_blocks,
            },
        }
        
        queries.append(new_record)
        
        # Recompute aggregates from full list
        latencies = [q["latency_seconds"] for q in queries]
        docs_list = [q["docs_returned"] for q in queries]
        files_list = [q["diversity"]["unique_files"] for q in queries]
        symbols_list = [q["diversity"]["unique_symbols"] for q in queries]
        words_list = [q["answer_metrics"]["answer_length_words"] for q in queries]
        expansions = [q["graph_expansion"]["expansion_ratio"] for q in queries if q["graph_expansion"]["expansion_ratio"] > 0]
        
        method_dist = defaultdict(int)
        for q in queries:
            method_dist[q["method"]] += 1
        
        queries_with_expansion = sum(1 for q in queries if q["graph_expansion"]["anchor_nodes"] > 0)
        queries_with_code = sum(1 for q in queries if q["answer_metrics"]["has_code_blocks"])
        
        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            idx = int(len(sorted_data) * p / 100)
            return sorted_data[min(idx, len(sorted_data) - 1)]
        
        aggregate = {
            "total_queries": len(queries),
            "avg_latency_seconds": round(mean(latencies), 2),
            "p50_latency_seconds": round(percentile(latencies, 50), 2),
            "p95_latency_seconds": round(percentile(latencies, 95), 2),
            "max_latency_seconds": round(max(latencies), 2),
            "min_latency_seconds": round(min(latencies), 2),
            "avg_docs_returned": round(mean(docs_list), 2),
            "avg_unique_files": round(mean(files_list), 2),
            "avg_unique_symbols": round(mean(symbols_list), 2),
            "avg_answer_length_words": round(mean(words_list), 2),
            "avg_expansion_ratio": round(mean(expansions), 2) if expansions else 0,
            "method_distribution": dict(method_dist),
            "queries_with_graph_expansion": queries_with_expansion,
            "queries_with_code_blocks": queries_with_code,
        }
        
        # Write back complete file
        output = {
            "repo_name": repo_name,
            "last_updated": _utc_now(),
            "queries": queries,
            "aggregate": aggregate,
        }
        with open(dest, "w") as f:
            json.dump(output, f, indent=2, default=str)
        _save_evaluation_data(repo_name, "retrieval_metrics.json", output)
            
    except Exception as e:
        print(f"[Evaluation] Warning: Failed to save retrieval metrics: {e}")


def save_code_health_metrics(
    repo_name: str,
    overall_score: float,
    grade: str,
    dimension_scores: dict,
    repository_stats: dict,
    smell_summary: dict,
    suggestion_count: int,
    file_score_distribution: dict,
):
    """Save code health analysis. Called from visualization.py."""
    try:
        metrics = {
            "repo_name": repo_name,
            "timestamp": _utc_now(),
            "overall_score": round(overall_score, 1),
            "grade": grade,
            "dimension_scores": {k: round(v, 1) for k, v in dimension_scores.items()},
            "repository_stats": repository_stats,
            "smell_summary": smell_summary,
            "suggestion_count": suggestion_count,
            "file_score_distribution": file_score_distribution,
        }
        
        dest = os.path.join(_eval_dir(repo_name), "code_health_metrics.json")
        with open(dest, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        _save_evaluation_data(repo_name, "code_health_metrics.json", metrics)
    except Exception as e:
        print(f"[Evaluation] Warning: Failed to save code health metrics: {e}")


def save_contribution_metrics(
    repo_name: str,
    repo_path: str = "",
    total_authors: int = 0,
    total_commits: int = 0,
    total_lines_added: int = 0,
    total_lines_deleted: int = 0,
    total_files_changed: int = 0,
    top_contributor_share_pct: float = 0,
    commit_sample_size: int = 0,
    detail_commit_sample_size: int = 0,
    fallback_mode: bool = False,
    timed_out: bool = False,
    has_line_stats: bool = False,
    has_file_stats: bool = False,
):
    """Save contribution extraction data. Called from ingest.py."""
    try:
        # Count actual repository lines of code
        actual_loc = _count_repository_lines_of_code(repo_path) if repo_path else {}
        
        metrics = {
            "repo_name": repo_name,
            "timestamp": _utc_now(),
            "contribution_summary": {
                "total_authors": total_authors,
                "total_commits": total_commits,
                "top_contributor_share_pct": round(top_contributor_share_pct, 1),
            },
            "git_history_metrics": {
                "git_cumulative_lines_added": total_lines_added,
                "git_cumulative_lines_deleted": total_lines_deleted,
                "git_net_cumulative_lines": total_lines_added - total_lines_deleted,
                "files_changed_in_history": total_files_changed,
                "note": "Git metrics are cumulative across all commits and can be inflated by large initial additions/deletions",
            },
            "repository_current_state": {
                "actual_lines_of_code": actual_loc.get("total_lines", 0),
                "total_source_files": actual_loc.get("total_files", 0),
                "lines_by_language": actual_loc.get("by_language", {}),
            },
            "data_completeness": {
                "commit_sample_size": commit_sample_size,
                "detail_commit_sample_size": detail_commit_sample_size,
                "fallback_mode": fallback_mode,
                "timed_out": timed_out,
                "has_line_stats": has_line_stats,
                "has_file_stats": has_file_stats,
            },
        }
        
        dest = os.path.join(_eval_dir(repo_name), "contribution_metrics.json")
        with open(dest, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        _save_evaluation_data(repo_name, "contribution_metrics.json", metrics)
    except Exception as e:
        print(f"[Evaluation] Warning: Failed to save contribution metrics: {e}")


def save_graph_metrics(
    repo_name: str,
    call_graph: dict,
    kg_builder,
    symbol_resolver,
):
    """Save knowledge graph and call graph structural stats. Called from ingest.py."""
    try:
        # Call graph stats
        total_callers = len(call_graph)
        total_edges_cg = sum(len(callees) for callees in call_graph.values())
        unique_callees = set()
        for callees in call_graph.values():
            unique_callees.update(callees)
        total_nodes_cg = total_callers + len(unique_callees)
        
        avg_fan_out = total_edges_cg / max(total_callers, 1)
        max_fan_out = max((len(callees) for callees in call_graph.values()), default=0)
        
        # Density: edges / (n * (n-1) / 2)
        max_edges = total_nodes_cg * (total_nodes_cg - 1) / 2 if total_nodes_cg > 1 else 1
        density = total_edges_cg / max_edges if max_edges > 0 else 0
        
        # KG stats
        kg_nodes = 0
        kg_edges = 0
        kg_edge_types = defaultdict(int)
        kg_node_types = defaultdict(int)
        
        if kg_builder and hasattr(kg_builder, "graph"):
            try:
                kg_nodes = len(kg_builder.graph.nodes)
                kg_edges = len(kg_builder.graph.edges)
                
                for edge in kg_builder.graph.edges:
                    kg_edge_types[edge.edge_type] += 1
                
                for node in kg_builder.graph.nodes.values():
                    kg_node_types[node.node_type] += 1
            except Exception:
                pass
        
        avg_kg_edges_per_node = kg_edges / max(kg_nodes, 1)
        
        # Symbol table stats
        total_files = 0
        files_with_symbols = 0
        total_symbols = 0
        symbol_kinds = defaultdict(int)
        
        if symbol_resolver and hasattr(symbol_resolver, "symbol_tables"):
            files_with_symbols = len(symbol_resolver.symbol_tables)
            total_files = files_with_symbols
            
            for symbol_table in symbol_resolver.symbol_tables.values():
                if hasattr(symbol_table, "all_symbols"):
                    for symbol in symbol_table.all_symbols.values():
                        total_symbols += 1
                        symbol_kinds[symbol.kind] += 1
        
        symbol_coverage = (files_with_symbols / max(total_files, 1) * 100) if total_files > 0 else 0
        
        metrics = {
            "repo_name": repo_name,
            "timestamp": _utc_now(),
            "call_graph": {
                "total_callers": total_callers,
                "total_nodes": total_nodes_cg,
                "total_edges": total_edges_cg,
                "avg_fan_out": round(avg_fan_out, 2),
                "max_fan_out": max_fan_out,
                "density": round(density, 4),
            },
            "knowledge_graph": {
                "total_nodes": kg_nodes,
                "total_edges": kg_edges,
                "edge_types": dict(kg_edge_types),
                "node_types": dict(kg_node_types),
                "avg_edges_per_node": round(avg_kg_edges_per_node, 2),
            },
            "symbol_table": {
                "total_files": total_files,
                "files_with_symbols": files_with_symbols,
                "total_symbols": total_symbols,
                "symbol_coverage_pct": round(symbol_coverage, 1),
                "symbol_kinds": dict(symbol_kinds),
            },
        }
        
        dest = os.path.join(_eval_dir(repo_name), "graph_metrics.json")
        with open(dest, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        _save_evaluation_data(repo_name, "graph_metrics.json", metrics)
    except Exception as e:
        print(f"[Evaluation] Warning: Failed to save graph metrics: {e}")


def load_evaluation_summary(repo_name: str) -> dict:
    """Load and combine all metric files into one summary dict."""
    summary = {"repo_name": repo_name, "files": {}}
    metric_files = [
        "ingestion_metrics.json",
        "retrieval_metrics.json",
        "code_health_metrics.json",
        "contribution_metrics.json",
        "graph_metrics.json",
    ]
    
    for metric_file in metric_files:
        try:
            data = _load_evaluation_data(repo_name, metric_file)
            if not data:
                continue
            if metric_file == "retrieval_metrics.json" and "aggregate" in data:
                summary["files"][metric_file] = {"aggregate": data["aggregate"]}
            else:
                summary["files"][metric_file] = data
        except Exception as e:
            print(f"[Evaluation] Warning: Failed to load {metric_file}: {e}")
    
    return summary
