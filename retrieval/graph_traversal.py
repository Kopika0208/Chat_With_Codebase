"""
Graph Traversal Module for Graph-RAG

Implements BFS/DFS graph traversal to expand context from anchor nodes.
Used to traverse the knowledge graph and find related code.
"""

import json
from typing import Set, List, Dict, Optional, Deque
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class TraversalStrategy(Enum):
    """Graph traversal strategy."""
    BFS = "bfs"  # Breadth-first search
    DFS = "dfs"  # Depth-first search


@dataclass
class TraversalResult:
    """Result of a graph traversal operation."""
    anchor_nodes: Set[str]  # Starting nodes
    visited_nodes: Set[str]  # All visited nodes
    reached_nodes_by_depth: Dict[int, Set[str]]  # Nodes grouped by depth
    edges_traversed: List[tuple]  # (source, target, edge_type) tuples
    
    def get_all_nodes(self) -> Set[str]:
        """Get all visited nodes."""
        return self.visited_nodes
    
    def get_nodes_at_depth(self, depth: int) -> Set[str]:
        """Get nodes at a specific depth."""
        return self.reached_nodes_by_depth.get(depth, set())
    
    def to_dict(self) -> Dict:
        """Convert to dict for serialization."""
        return {
            "anchor_nodes": list(self.anchor_nodes),
            "visited_nodes": list(self.visited_nodes),
            "nodes_by_depth": {str(k): list(v) for k, v in self.reached_nodes_by_depth.items()},
            "edge_count": len(self.edges_traversed),
        }


class GraphTraversal:
    """Graph traversal engine for knowledge graph exploration.
    
    Performs BFS or DFS from anchor nodes to expand context, optionally
    filtering by edge types.
    """
    
    def __init__(self, knowledge_graph_data: Dict):
        """Initialize traversal engine.
        
        Args:
            knowledge_graph_data: Dict with "nodes" list and "edges" list
        """
        self.nodes = {}  # node_id -> node data
        self.adjacency_out = {}  # node_id -> [(target_id, edge_type, properties)]
        self.adjacency_in = {}  # node_id -> [(source_id, edge_type, properties)]
        
        self._build_indexes(knowledge_graph_data)
    
    def _build_indexes(self, kg_data: Dict) -> None:
        """Build adjacency indexes from knowledge graph data."""
        # Index nodes - handle both list and dict formats
        nodes_data = kg_data.get("nodes", [])
        
        if isinstance(nodes_data, dict):
            # Dict format: {node_id: node_info}
            for node_id, node in nodes_data.items():
                self.nodes[node_id] = node
                self.adjacency_out[node_id] = []
                self.adjacency_in[node_id] = []
        else:
            # List format: [{"id": node_id, ...}]
            for node in nodes_data:
                node_id = node.get("id") or node.get("node_id")
                self.nodes[node_id] = node
                self.adjacency_out[node_id] = []
                self.adjacency_in[node_id] = []
        
        # Index edges
        for edge in kg_data.get("edges", []):
            source_id = edge.get("source")
            target_id = edge.get("target")
            edge_type = edge.get("type")
            properties = edge.get("properties", {})
            
            if source_id not in self.adjacency_out:
                self.adjacency_out[source_id] = []
            if target_id not in self.adjacency_in:
                self.adjacency_in[target_id] = []
            
            self.adjacency_out[source_id].append((target_id, edge_type, properties))
            self.adjacency_in[target_id].append((source_id, edge_type, properties))
    
    def traverse(
        self,
        anchor_nodes: Set[str],
        max_depth: int = 2,
        strategy: TraversalStrategy = TraversalStrategy.BFS,
        edge_types: Optional[List[str]] = None,
        direction: str = "both"  # "out", "in", or "both"
    ) -> TraversalResult:
        """Traverse the graph from anchor nodes.
        
        Args:
            anchor_nodes: Starting node IDs
            max_depth: Maximum traversal depth (default 2)
            strategy: BFS or DFS
            edge_types: Filter by edge types, e.g., ["calls", "called_by"]
            direction: "out" (outgoing), "in" (incoming), or "both"
        
        Returns:
            TraversalResult with visited nodes and edges
        """
        if not anchor_nodes:
            return TraversalResult(set(), set(), {}, [])
        
        # Ensure anchor nodes exist in graph
        anchor_nodes = {n for n in anchor_nodes if n in self.nodes}
        
        if strategy == TraversalStrategy.BFS:
            return self._bfs(anchor_nodes, max_depth, edge_types, direction)
        else:
            return self._dfs(anchor_nodes, max_depth, edge_types, direction)
    
    def _bfs(
        self,
        anchor_nodes: Set[str],
        max_depth: int,
        edge_types: Optional[List[str]],
        direction: str
    ) -> TraversalResult:
        """Breadth-first search traversal."""
        visited = set(anchor_nodes)
        reached_by_depth = {0: set(anchor_nodes)}
        edges_traversed = []
        
        queue: Deque[tuple] = deque((node, 0) for node in anchor_nodes)
        
        while queue:
            current_node, depth = queue.popleft()
            
            if depth >= max_depth:
                continue
            
            # Get neighbors
            neighbors = self._get_neighbors(current_node, edge_types, direction)
            
            next_depth = depth + 1
            if next_depth not in reached_by_depth:
                reached_by_depth[next_depth] = set()
            
            for neighbor_id, edge_type, edge_props in neighbors:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    reached_by_depth[next_depth].add(neighbor_id)
                    queue.append((neighbor_id, next_depth))
                    edges_traversed.append((current_node, neighbor_id, edge_type))
        
        return TraversalResult(
            anchor_nodes=anchor_nodes,
            visited_nodes=visited,
            reached_nodes_by_depth=reached_by_depth,
            edges_traversed=edges_traversed
        )
    
    def _dfs(
        self,
        anchor_nodes: Set[str],
        max_depth: int,
        edge_types: Optional[List[str]],
        direction: str
    ) -> TraversalResult:
        """Depth-first search traversal."""
        visited = set()
        reached_by_depth = {}
        edges_traversed = []
        
        def dfs_helper(node: str, depth: int):
            if depth > max_depth:
                return
            
            if node in visited:
                return
            
            visited.add(node)
            if depth not in reached_by_depth:
                reached_by_depth[depth] = set()
            reached_by_depth[depth].add(node)
            
            # Get neighbors
            neighbors = self._get_neighbors(node, edge_types, direction)
            
            for neighbor_id, edge_type, edge_props in neighbors:
                if neighbor_id not in visited:
                    edges_traversed.append((node, neighbor_id, edge_type))
                    dfs_helper(neighbor_id, depth + 1)
        
        # Start from all anchor nodes
        for anchor in anchor_nodes:
            if anchor not in visited:
                dfs_helper(anchor, 0)
        
        return TraversalResult(
            anchor_nodes=anchor_nodes,
            visited_nodes=visited,
            reached_nodes_by_depth=reached_by_depth,
            edges_traversed=edges_traversed
        )
    
    def _get_neighbors(
        self,
        node_id: str,
        edge_types: Optional[List[str]],
        direction: str
    ) -> List[tuple]:
        """Get neighbors of a node, optionally filtered by edge type."""
        neighbors = []
        
        if direction in ("out", "both"):
            for target_id, edge_type, props in self.adjacency_out.get(node_id, []):
                if edge_types is None or edge_type in edge_types:
                    neighbors.append((target_id, edge_type, props))
        
        if direction in ("in", "both"):
            for source_id, edge_type, props in self.adjacency_in.get(node_id, []):
                if edge_types is None or edge_type in edge_types:
                    neighbors.append((source_id, edge_type, props))
        
        return neighbors
    
    def find_paths(
        self,
        source: str,
        target: str,
        max_length: int = 5,
        edge_types: Optional[List[str]] = None
    ) -> List[List[str]]:
        """Find all paths between two nodes.
        
        Args:
            source: Source node ID
            target: Target node ID
            max_length: Maximum path length
            edge_types: Filter by edge types
        
        Returns:
            List of paths (each path is a list of node IDs)
        """
        if source not in self.nodes or target not in self.nodes:
            return []
        
        paths = []
        
        def dfs_path(current: str, target: str, path: List[str], visited: Set[str]):
            if len(path) > max_length:
                return
            
            if current == target:
                paths.append(path[:])
                return
            
            for neighbor_id, edge_type, _ in self.adjacency_out.get(current, []):
                if neighbor_id not in visited:
                    if edge_types is None or edge_type in edge_types:
                        visited.add(neighbor_id)
                        path.append(neighbor_id)
                        dfs_path(neighbor_id, target, path, visited)
                        path.pop()
                        visited.remove(neighbor_id)
        
        visited = {source}
        dfs_path(source, target, [source], visited)
        
        return paths
    
    def get_node_info(self, node_id: str) -> Optional[Dict]:
        """Get information about a node."""
        return self.nodes.get(node_id)
    
    def get_node_context(
        self,
        node_id: str,
        radius: int = 1,
        edge_types: Optional[List[str]] = None
    ) -> Dict:
        """Get node and its immediate neighbors.
        
        Args:
            node_id: Target node
            radius: Radius around the node (1 = direct neighbors)
            edge_types: Filter by edge types
        
        Returns:
            Dict with node info and neighbors
        """
        node_info = self.get_node_info(node_id)
        if not node_info:
            return {}
        
        result = self.traverse(
            {node_id},
            max_depth=radius,
            edge_types=edge_types,
            direction="both"
        )
        
        return {
            "node": node_info,
            "neighbors": [self.nodes.get(n) for n in result.visited_nodes if n != node_id],
            "traversal_result": result.to_dict(),
        }


def load_knowledge_graph(path: str) -> "GraphTraversal":
    """Load knowledge graph from JSON and create traversal engine.
    
    Args:
        path: Path to knowledge_graph.json
    
    Returns:
        GraphTraversal instance
    """
    with open(path, "r", encoding="utf-8") as f:
        kg_data = json.load(f)
    
    # Handle both formats: plain {"nodes": [...], "edges": [...]} and {"metadata": {...}, "nodes": [...], "edges": [...]}
    if "nodes" not in kg_data and "metadata" in kg_data:
        # Old format with metadata at top level - extract nodes and edges
        graph_data = {
            "nodes": kg_data.get("nodes", []),
            "edges": kg_data.get("edges", [])
        }
    else:
        # Use as-is
        graph_data = kg_data
    
    return GraphTraversal(graph_data)
