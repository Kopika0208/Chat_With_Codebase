"""Onboarding data endpoints - overview, entry points, file tree, roadmap."""

import os
import sys
from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.deps import (
    list_repos, load_call_graph, load_symbol_table,
    load_knowledge_graph, load_dataflow,
    load_boot_chain, load_core_structures,
    load_documentation, get_repo_source_path, get_repo_summary,
)

router = APIRouter(prefix="/api/repos/{repo_name}/onboarding", tags=["onboarding"])


@router.get("/overview")
def get_overview(repo_name: str):
    """Get project overview stats and summary."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    summary = get_repo_summary(repo_name)
    boot_chain = load_boot_chain(repo_name)
    core_structures = load_core_structures(repo_name)
    kg = load_knowledge_graph(repo_name)

    # Detect languages from symbol table
    symbol_table = load_symbol_table(repo_name)
    lang_counts = {}
    file_symbols = symbol_table.get("file_symbols", {})
    for file_key in file_symbols:
        clean = file_key.split(":")[-1] if ":" in file_key else file_key
        ext = os.path.splitext(clean)[1].lower()
        lang_map = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
                    ".java": "Java", ".go": "Go", ".rs": "Rust",
                    ".cpp": "C++", ".c": "C"}
        lang = lang_map.get(ext)
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    total_files = sum(lang_counts.values()) or 1
    language_distribution = [
        {"language": lang, "count": count, "percentage": round(count / total_files * 100, 1)}
        for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])
    ]

    documentation = load_documentation(repo_name).get("content", "")

    return {
        "summary": summary,
        "documentation": documentation,
        "language_distribution": language_distribution,
        "has_boot_chain": bool(boot_chain and boot_chain.get("ordered_steps")),
        "core_structures_count": len(core_structures.get("structures", [])),
        "kg_nodes": len(kg.get("nodes", [])) if isinstance(kg.get("nodes"), (list, dict)) else 0,
        "kg_edges": len(kg.get("edges", [])) if isinstance(kg.get("edges"), list) else 0,
    }


@router.get("/entry-points")
def get_entry_exit_points(repo_name: str):
    """Get entry and exit points for the codebase."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    call_graph = load_call_graph(repo_name)
    boot_chain = load_boot_chain(repo_name)

    if not call_graph:
        return {"entry_points": [], "exit_points": []}

    # Entry points: functions that call others but aren't called by anyone
    callers = set(call_graph.keys())
    called = set()
    for callees in call_graph.values():
        callee_list = list(callees) if isinstance(callees, (set, list)) else [callees]
        called.update(callee_list)

    entry_points = []
    for node in callers - called:
        name = node.split(":")[-1] if ":" in node else node
        file = node.split(":")[0] if ":" in node else ""
        callees = call_graph.get(node, [])
        fan_out = len(list(callees) if isinstance(callees, (set, list)) else [callees])
        entry_points.append({
            "name": name,
            "full_id": node,
            "file": file,
            "fan_out": fan_out,
            "type": "boot_entry" if any(
                name.lower() in str(s.get("name", "")).lower()
                for s in boot_chain.get("entry_points", [])
            ) else "entry",
        })

    entry_points.sort(key=lambda x: (-x["fan_out"], x["name"]))

    # Exit points: functions that are called but don't call anything
    exit_points = []
    for node in called - callers:
        name = node.split(":")[-1] if ":" in node else node
        file = node.split(":")[0] if ":" in node else ""
        # Count how many callers
        fan_in = sum(
            1 for callees in call_graph.values()
            if node in (list(callees) if isinstance(callees, (set, list)) else [callees])
        )
        exit_points.append({
            "name": name,
            "full_id": node,
            "file": file,
            "fan_in": fan_in,
            "type": "leaf",
        })

    exit_points.sort(key=lambda x: (-x["fan_in"], x["name"]))

    return {
        "entry_points": entry_points[:20],
        "exit_points": exit_points[:20],
    }


@router.get("/file-tree")
def get_file_tree(repo_name: str):
    """Get file tree structure from symbol table."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    symbol_table = load_symbol_table(repo_name)
    file_symbols = symbol_table.get("file_symbols", {})

    tree = {}
    for file_key, file_data in file_symbols.items():
        clean_path = file_key.split(":", 1)[1] if ":" in file_key else file_key
        parts = clean_path.replace("\\", "/").split("/")

        # Count symbols in this file
        symbols = file_data.get("symbols", {}) if isinstance(file_data, dict) else {}
        func_count = sum(1 for s in symbols.values() if isinstance(s, dict) and s.get("kind") in ("function", "method"))
        class_count = sum(1 for s in symbols.values() if isinstance(s, dict) and s.get("kind") == "class")

        # Build nested tree
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # File node
                current[part] = {
                    "_type": "file",
                    "_path": clean_path,
                    "_functions": func_count,
                    "_classes": class_count,
                    "_symbols": len(symbols),
                }
            else:
                # Directory node
                if part not in current:
                    current[part] = {}
                current = current[part]

    return {"tree": tree, "total_files": len(file_symbols)}


@router.get("/roadmap")
def get_roadmap(repo_name: str):
    """Get learning roadmap based on dependency order."""
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    call_graph = load_call_graph(repo_name)
    if not call_graph:
        return {"steps": [], "summary": "No call graph data available."}

    # Group functions by file/module
    file_deps = {}  # file -> set of files it depends on
    file_functions = {}  # file -> list of function names

    for caller, callees in call_graph.items():
        caller_file = caller.split(":")[0] if ":" in caller else "unknown"
        caller_name = caller.split(":")[-1] if ":" in caller else caller

        file_functions.setdefault(caller_file, []).append(caller_name)
        file_deps.setdefault(caller_file, set())

        callee_list = list(callees) if isinstance(callees, (set, list)) else [callees]
        for callee in callee_list:
            callee_file = callee.split(":")[0] if ":" in callee else "unknown"
            if callee_file != caller_file:
                file_deps[caller_file].add(callee_file)

    # Topological-ish sort: files with fewer dependencies come first
    sorted_files = sorted(
        file_deps.items(),
        key=lambda x: (len(x[1]), x[0])
    )

    steps = []
    for i, (file_path, deps) in enumerate(sorted_files[:15], 1):
        clean = file_path.split(":", 1)[1] if ":" in file_path else file_path
        functions = file_functions.get(file_path, [])
        steps.append({
            "step": i,
            "file": clean,
            "functions": functions[:10],
            "dependency_count": len(deps),
            "depends_on": [d.split(":", 1)[1] if ":" in d else d for d in sorted(deps)[:5]],
        })

    return {
        "steps": steps,
        "total_modules": len(file_deps),
        "summary": f"Learning roadmap with {len(steps)} modules ordered by dependency complexity.",
    }
