"""Call graph data endpoint."""

from fastapi import APIRouter, HTTPException
from backend.deps import list_repos, load_call_graph, load_symbol_table

router = APIRouter(prefix="/api/repos/{repo_name}", tags=["callgraph"])


@router.get("/callgraph")
def get_callgraph(repo_name: str, focus: str = None, max_depth: int = 2, exclude_external: bool = True):
    """
    Get call graph data for visualization.
    
    Args:
        repo_name: Repository name
        focus: Optional function name to focus on
        max_depth: Max depth from focus node (default 2)
        exclude_external: If True (default), exclude unresolved external calls
    
    Returns:
        Nodes and edges for graph rendering
    """
    if repo_name not in list_repos():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

    call_graph = load_call_graph(repo_name)
    if not call_graph:
        return {"nodes": [], "edges": [], "stats": {}}

    # Load symbol table to identify repo symbols
    symbol_table = load_symbol_table(repo_name)
    repo_symbols = set()
    if symbol_table:
        global_index = symbol_table.get("global_index", {})
        all_symbols_list = global_index.get("all_symbols", [])
        for entry in all_symbols_list:
            if isinstance(entry, dict) and "fqn" in entry:
                repo_symbols.add(entry["fqn"])

    # Build full node set and edges, filtering external calls if requested
    all_nodes = set()
    edges = []
    
    for caller, callees in call_graph.items():
        all_nodes.add(caller)
        callee_list = list(callees) if isinstance(callees, (set, list)) else [callees]
        for callee in callee_list:
            # Filter: only keep edges where callee is a repo symbol (has ':')
            # This removes external/unresolved calls like 'len', 'strip', 'open'
            if exclude_external:
                if ":" not in callee:
                    continue  # Skip external names
            
            all_nodes.add(callee)
            edges.append({"source": caller, "target": callee})

    # If focus is specified, filter to subgraph
    if focus:
        # Find the focus node (fuzzy match)
        focus_node = None
        focus_lower = focus.lower()
        for node in all_nodes:
            if focus_lower in node.lower():
                focus_node = node
                break

        if focus_node:
            # BFS to find nodes within max_depth
            visible = {focus_node}
            frontier = {focus_node}
            for _ in range(max_depth):
                next_frontier = set()
                for node in frontier:
                    # Outgoing
                    for callee in (call_graph.get(node) or []):
                        if exclude_external and ":" not in callee:
                            continue
                        next_frontier.add(callee)
                    # Incoming
                    for caller, callees in call_graph.items():
                        callee_list = list(callees) if isinstance(callees, (set, list)) else [callees]
                        if node in callee_list:
                            if exclude_external and ":" not in node:
                                continue
                            next_frontier.add(caller)
                visible.update(next_frontier)
                frontier = next_frontier

            # Filter edges to visible nodes
            edges = [e for e in edges if e["source"] in visible and e["target"] in visible]
            all_nodes = visible

    # Classify nodes
    callers_set = set(call_graph.keys())
    called_set = set()
    for callees in call_graph.values():
        callee_list = list(callees) if isinstance(callees, (set, list)) else [callees]
        if exclude_external:
            callee_list = [c for c in callee_list if ":" in c]
        called_set.update(callee_list)

    nodes = []
    for node_id in all_nodes:
        # Extract short name
        name = node_id.split(":")[-1] if ":" in node_id else node_id

        # Classify: entry (not called by anyone), core (both calls and called), helper (leaf)
        is_caller = node_id in callers_set
        is_called = node_id in called_set
        if is_caller and not is_called:
            node_type = "entry"
        elif is_caller and is_called:
            node_type = "core"
        else:
            node_type = "helper"

        nodes.append({
            "id": node_id,
            "label": name,
            "type": node_type,
            "file": node_id.split(":")[0] if ":" in node_id else "",
        })

    # Stats
    fan_outs = []
    for v in call_graph.values():
        callee_list = list(v) if isinstance(v, (set, list)) else [v]
        if exclude_external:
            callee_list = [c for c in callee_list if ":" in c]
        fan_outs.append(len(callee_list))
    
    stats = {
        "total_functions": len(all_nodes),
        "total_edges": len(edges),
        "entry_points": sum(1 for n in nodes if n["type"] == "entry"),
        "max_fan_out": max(fan_outs) if fan_outs else 0,
        "external_excluded": exclude_external,
    }

    return {"nodes": nodes, "edges": edges, "stats": stats}
