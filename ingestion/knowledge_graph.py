# knowledge_graph.py - Knowledge graph builder and related classes

import ast
import re
import json
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from .symbols import Symbol, SymbolTable


@dataclass
class KnowledgeGraphNode:
    """Represents a node in the knowledge graph.
    
    Stable node IDs are in format: file.py:symbol_name or file.js:ClassName.method
    """
    node_id: str  # unique identifier: file:symbol (stable)
    node_type: str  # "function", "class", "method", "variable", "module", "import"
    name: str  # short name
    file_path: str
    line_number: int
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.node_id)
    
    def __eq__(self, other):
        if isinstance(other, KnowledgeGraphNode):
            return self.node_id == other.node_id
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "file": self.file_path,
            "line": self.line_number,
            "properties": self.properties,
        }


@dataclass
class KnowledgeGraphEdge:
    """Represents an edge in the knowledge graph.
    
    Edge types: calls, called_by, defines, uses, dataflow, 
               inherits, overrides, sibling_method, test_relationship, contains
    """
    source_id: str
    target_id: str
    edge_type: str  # typed relationship
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash((self.source_id, self.target_id, self.edge_type))
    
    def __eq__(self, other):
        if isinstance(other, KnowledgeGraphEdge):
            return (self.source_id == other.source_id and
                    self.target_id == other.target_id and
                    self.edge_type == other.edge_type)
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type,
            "properties": self.properties,
        }


class KnowledgeGraph:
    """Comprehensive knowledge graph for codebase understanding.
    
    Stores nodes (symbols) and typed edges (relationships):
    - calls / called_by: function call relationships
    - dataflow: data flow dependencies
    - defines / uses: definition-use relationships
    - inherits / overrides: class hierarchy
    - sibling_method: class methods
    - test_relationship: test ↔ production code
    - contains: parent-child relationships
    """
    
    def __init__(self):
        self.nodes: Dict[str, KnowledgeGraphNode] = {}
        self.edges: Set[KnowledgeGraphEdge] = set()
        # Adjacency index: node_id -> List of outgoing edges
        self.adjacency_out: Dict[str, List[KnowledgeGraphEdge]] = defaultdict(list)
        # Reverse adjacency: node_id -> List of incoming edges
        self.adjacency_in: Dict[str, List[KnowledgeGraphEdge]] = defaultdict(list)
    
    def add_node(self, node: KnowledgeGraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
    
    def add_edge(self, edge: KnowledgeGraphEdge) -> None:
        """Add an edge to the graph, avoiding duplicates."""
        if edge not in self.edges:
            self.edges.add(edge)
            self.adjacency_out[edge.source_id].append(edge)
            self.adjacency_in[edge.target_id].append(edge)
    
    def get_node(self, node_id: str) -> Optional[KnowledgeGraphNode]:
        """Retrieve a node by ID."""
        return self.nodes.get(node_id)
    
    def get_outgoing_edges(self, node_id: str, edge_type: Optional[str] = None) -> List[KnowledgeGraphEdge]:
        """Get all outgoing edges from a node, optionally filtered by type."""
        edges = self.adjacency_out.get(node_id, [])
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges
    
    def get_incoming_edges(self, node_id: str, edge_type: Optional[str] = None) -> List[KnowledgeGraphEdge]:
        """Get all incoming edges to a node, optionally filtered by type."""
        edges = self.adjacency_in.get(node_id, [])
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges
    
    def get_neighbors(self, node_id: str, edge_types: Optional[List[str]] = None,
                     direction: str = "both") -> Set[str]:
        """Get all neighbor node IDs, optionally filtered by edge types.
        
        Args:
            node_id: The node to find neighbors for
            edge_types: Filter by edge types, e.g., ["calls", "called_by"]
            direction: "out" (outgoing), "in" (incoming), or "both"
        
        Returns:
            Set of neighbor node IDs
        """
        neighbors = set()
        
        if direction in ("out", "both"):
            for edge in self.get_outgoing_edges(node_id):
                if edge_types is None or edge.edge_type in edge_types:
                    neighbors.add(edge.target_id)
        
        if direction in ("in", "both"):
            for edge in self.get_incoming_edges(node_id):
                if edge_types is None or edge.edge_type in edge_types:
                    neighbors.add(edge.source_id)
        
        return neighbors
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export graph as dictionary for JSON serialization."""
        return {
            "metadata": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "version": "1.0",
            },
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    def compute_node_importance(self, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Rank nodes by a simple centrality-style score using graph connectivity."""
        ranked = []

        for node_id, node in self.nodes.items():
            outgoing = self.adjacency_out.get(node_id, [])
            incoming = self.adjacency_in.get(node_id, [])
            edge_types = {edge.edge_type for edge in outgoing + incoming}

            score = (
                len(outgoing) * 1.2
                + len(incoming) * 1.0
                + len(edge_types) * 1.5
            )

            ranked.append({
                "id": node_id,
                "name": node.name,
                "type": node.node_type,
                "file": node.file_path,
                "line": node.line_number,
                "out_degree": len(outgoing),
                "in_degree": len(incoming),
                "edge_types": sorted(edge_types),
                "importance_score": round(score, 3),
            })

        ranked.sort(
            key=lambda item: (
                -item["importance_score"],
                -item["out_degree"],
                -item["in_degree"],
                item["name"],
            )
        )
        return ranked[:top_k] if top_k else ranked
    
    def to_json(self, path: str) -> None:
        """Persist graph to JSON file."""
        data = self.export_to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, path: str) -> "KnowledgeGraph":
        """Load graph from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        graph = cls()
        
        # Load nodes
        for node_data in data.get("nodes", []):
            node = KnowledgeGraphNode(
                node_id=node_data["id"],
                node_type=node_data["type"],
                name=node_data["name"],
                file_path=node_data["file"],
                line_number=node_data["line"],
                properties=node_data.get("properties", {}),
            )
            graph.add_node(node)
        
        # Load edges
        for edge_data in data.get("edges", []):
            edge = KnowledgeGraphEdge(
                source_id=edge_data["source"],
                target_id=edge_data["target"],
                edge_type=edge_data["type"],
                properties=edge_data.get("properties", {}),
            )
            graph.add_edge(edge)
        
        return graph



class KnowledgeGraphBuilder:
    """Build comprehensive knowledge graph from symbol tables, call graphs, and data flow.
    
    Extracts:
    - Function/class definitions (nodes)
    - Call relationships (calls, called_by)
    - Data flow (defines, uses, dataflow)
    - Class hierarchy (inherits, overrides)
    - Test relationships (test_relationship)
    - Attribute access (uses)
    """
    
    def __init__(self):
        self.graph = KnowledgeGraph()
        self.class_hierarchy: Dict[str, List[str]] = {}
        self.method_map: Dict[str, Dict[str, str]] = {}
        self.test_methods: Dict[str, str] = {}
    
    def build_from_symbols(self, symbol_tables: Dict[str, SymbolTable]) -> None:
        """Build graph from symbol tables."""
        print("🏗️ Building knowledge graph from symbol tables...")
        
        # First pass: add all symbol nodes
        for file_path, symbol_table in symbol_tables.items():
            for fqn, symbol in symbol_table.all_symbols.items():
                node = KnowledgeGraphNode(
                    node_id=fqn,
                    node_type=symbol.kind,
                    name=symbol.name,
                    file_path=file_path,
                    line_number=symbol.line_number,
                    properties={
                        "is_private": symbol.is_private,
                        "is_static": symbol.is_static,
                        "docstring": symbol.docstring[:200] if symbol.docstring else None,
                        "parent_symbol": symbol.parent_symbol,
                    }
                )
                self.graph.add_node(node)
        
        # Second pass: add edges
        for file_path, symbol_table in symbol_tables.items():
            for fqn, symbol in symbol_table.all_symbols.items():
                self._build_symbol_edges(symbol, symbol_table, file_path)
        
        print(f"✅ Built graph with {len(self.graph.nodes)} nodes")
    
    def build_from_dataflow(
        self,
        dataflow_by_file: Dict[str, Dict[str, Any]],
        call_graph: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """Add dataflow relationships to the graph."""
        print("📊 Adding dataflow edges to knowledge graph...")
        
        for file_path, functions in dataflow_by_file.items():
            for func_name, analysis in functions.items():
                func_node_id = f"{file_path}:{func_name}"
                
                # Only add dataflow edges if the function node exists
                if func_node_id not in self.graph.nodes:
                    continue
                
                # Add def-use chain edges
                for chain_id, chain_data in analysis.get("def_use_chains", {}).items():
                    for use in chain_data.get("uses", []):
                        # Add dataflow edge to indicate data dependency
                        edge = KnowledgeGraphEdge(
                            source_id=func_node_id,
                            target_id=func_node_id,  # Self-loop for internal dataflow
                            edge_type="dataflow",
                            properties={
                                "variable": chain_id.split("@")[0],
                                "from_line": int(chain_id.split("@")[1]) if "@" in chain_id else 0,
                                "to_line": use.get("line", 0),
                            }
                        )
                        self.graph.add_edge(edge)

        if call_graph:
            self._add_interprocedural_dataflow(dataflow_by_file, call_graph)
    
    def _add_interprocedural_dataflow(
        self,
        dataflow_by_file: Dict[str, Dict[str, Any]],
        call_graph: Dict[str, List[str]],
    ) -> None:
        """Connect caller and callee functions with cross-boundary dataflow edges."""
        print("Adding inter-procedural dataflow edges...")

        function_analysis = {}
        for file_path, functions in dataflow_by_file.items():
            for func_name, analysis in functions.items():
                function_analysis[f"{file_path}:{func_name}"] = analysis

        edges_added = 0
        for caller_fqn, callees in call_graph.items():
            caller_analysis = function_analysis.get(caller_fqn)
            if not caller_analysis:
                continue

            for callee_fqn in callees:
                callee_analysis = function_analysis.get(callee_fqn)
                if not callee_analysis:
                    continue

                call_site = self._match_call_site(caller_analysis, callee_fqn)
                if not call_site:
                    continue

                self.graph.add_edge(
                    KnowledgeGraphEdge(
                        source_id=caller_fqn,
                        target_id=callee_fqn,
                        edge_type="dataflow",
                        properties={
                            "flow_kind": "interprocedural_call",
                            "call_line": call_site.get("line", 0),
                            "parameter_bindings": self._build_parameter_bindings(call_site, callee_analysis),
                            "assigned_to": call_site.get("assigned_to"),
                        }
                    )
                )
                edges_added += 1

                if call_site.get("assigned_to") and callee_analysis.get("returns"):
                    self.graph.add_edge(
                        KnowledgeGraphEdge(
                            source_id=callee_fqn,
                            target_id=caller_fqn,
                            edge_type="dataflow",
                            properties={
                                "flow_kind": "return_propagation",
                                "call_line": call_site.get("line", 0),
                                "assigned_to": call_site.get("assigned_to"),
                                "returns": callee_analysis.get("returns", []),
                            }
                        )
                    )
                    edges_added += 1

        print(f"Added {edges_added} inter-procedural dataflow edges")

    def _match_call_site(self, caller_analysis: Dict[str, Any], callee_fqn: str) -> Optional[Dict[str, Any]]:
        """Find the likely call site for a callee inside a caller function."""
        callee_short_name = callee_fqn.split(":")[-1]
        for site in caller_analysis.get("call_sites", []):
            if site.get("callee") == callee_short_name:
                return site
        return None

    def _build_parameter_bindings(self, call_site: Dict[str, Any], callee_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Zip positional and keyword caller arguments to callee parameters."""
        bindings = []
        parameters = callee_analysis.get("parameters", [])
        args = call_site.get("args", [])

        for index, parameter in enumerate(parameters):
            if index < len(args):
                arg = args[index]
                bindings.append({
                    "parameter": parameter.get("name"),
                    "argument_expr": arg.get("expr"),
                    "argument_name": arg.get("name"),
                    "argument_type": arg.get("type"),
                })

        for keyword in call_site.get("keywords", []):
            if keyword.get("name"):
                bindings.append({
                    "parameter": keyword.get("name"),
                    "argument_expr": keyword.get("expr"),
                    "argument_name": keyword.get("name"),
                    "argument_type": keyword.get("type"),
                })

        return bindings

    def add_call_graph(self, call_graph: Dict[str, List[str]]) -> None:
        """Add call graph as edges to the knowledge graph."""
        print("📞 Adding call graph edges to knowledge graph...")
        
        edges_added = 0
        for caller_fqn, callees in call_graph.items():
            if caller_fqn not in self.graph.nodes:
                continue
            
            for callee_fqn in callees:
                # Add "calls" edge
                edge = KnowledgeGraphEdge(
                    source_id=caller_fqn,
                    target_id=callee_fqn,
                    edge_type="calls",
                    properties={"call_count": 1}
                )
                self.graph.add_edge(edge)
                edges_added += 1
        
        print(f"✅ Added {edges_added} call graph edges")
    
    def _build_symbol_edges(self, symbol: Symbol, symbol_table: SymbolTable, file_path: str) -> None:
        """Build edges for a symbol based on scope and relationships."""
        fqn = symbol.fully_qualified_name
        
        # Inheritance edges
        scope = symbol_table.scopes.get(symbol.scope_id)
        if scope and scope.scope_type == "class" and scope.mro:
            for base_class in scope.mro:
                base_fqn = f"{file_path}:{base_class}" if ":" not in base_class else base_class
                if base_fqn in self.graph.nodes:
                    edge = KnowledgeGraphEdge(
                        source_id=fqn,
                        target_id=base_fqn,
                        edge_type="inherits",
                        properties={"mro_order": scope.mro.index(base_class)}
                    )
                    self.graph.add_edge(edge)
        
        # Parent-child relationship (method in class)
        if symbol.parent_symbol and ":" in symbol.parent_symbol:
            parent_fqn = symbol.parent_symbol
            if parent_fqn in self.graph.nodes:
                edge = KnowledgeGraphEdge(
                    source_id=parent_fqn,
                    target_id=fqn,
                    edge_type="contains",
                    properties={"member_type": symbol.kind}
                )
                self.graph.add_edge(edge)
    
    def add_test_relationships(self, test_map: Dict[str, str]) -> None:
        """Add edges between test and production code.
        
        Args:
            test_map: Dict mapping test node IDs to production node IDs
        """
        print("🧪 Adding test relationships...")
        
        for test_fqn, prod_fqn in test_map.items():
            if test_fqn in self.graph.nodes and prod_fqn in self.graph.nodes:
                edge = KnowledgeGraphEdge(
                    source_id=test_fqn,
                    target_id=prod_fqn,
                    edge_type="test_relationship",
                    properties={"direction": "tests"}
                )
                self.graph.add_edge(edge)
    
    def export(self, path: str) -> None:
        """Export the knowledge graph to JSON."""
        self.graph.to_json(path)
        print(f"💾 Knowledge graph saved to {path}")
    
    def get_graph(self) -> KnowledgeGraph:
        """Return the built knowledge graph."""
        return self.graph
    
    def add_override_relationships(self, symbol_tables: Dict[str, SymbolTable]) -> None:
        """Detect method overrides in inheritance hierarchies."""
        # Build a class hierarchy map
        class_methods: Dict[str, Set[str]] = defaultdict(set)
        
        for file_path, symbol_table in symbol_tables.items():
            for fqn, symbol in symbol_table.all_symbols.items():
                if symbol.kind == "method" and symbol.parent_symbol:
                    parent_fqn = symbol.parent_symbol
                    class_methods[parent_fqn].add(symbol.name)
        
        # Check for overrides
        for file_path, symbol_table in symbol_tables.items():
            for fqn, symbol in symbol_table.all_symbols.items():
                if symbol.kind == "class":
                    scope = symbol_table.scopes.get(symbol.scope_id)
                    if scope and scope.mro:
                        for base_class in scope.mro:
                            base_fqn = f"{file_path}:{base_class}" if ":" not in base_class else base_class
                            base_methods = class_methods.get(base_fqn, set())
                            
                            for method_name in class_methods.get(fqn, set()):
                                if method_name in base_methods:
                                    derived_method_fqn = f"{fqn}:{method_name}"
                                    base_method_fqn = f"{base_fqn}:{method_name}"
                                    
                                    if derived_method_fqn in self.graph.nodes and base_method_fqn in self.graph.nodes:
                                        edge = KnowledgeGraphEdge(
                                            source_id=derived_method_fqn,
                                            target_id=base_method_fqn,
                                            edge_type="overrides",
                                        )
                                        self.graph.add_edge(edge)
    
    def add_sibling_relationships(self, symbol_tables: Dict[str, SymbolTable]) -> None:
        """Add edges between sibling methods in the same class."""
        for file_path, symbol_table in symbol_tables.items():
            for fqn, symbol in symbol_table.all_symbols.items():
                if symbol.kind == "class":
                    # Find all methods in this class
                    methods = []
                    for candidate_fqn, candidate_symbol in symbol_table.all_symbols.items():
                        if candidate_symbol.kind == "method" and candidate_symbol.parent_symbol == fqn:
                            methods.append(candidate_fqn)
                    
                    # Add sibling edges between methods
                    for i, method1_fqn in enumerate(methods):
                        for method2_fqn in methods[i+1:]:
                            edge = KnowledgeGraphEdge(
                                source_id=method1_fqn,
                                target_id=method2_fqn,
                                edge_type="sibling_method",
                                properties={"class": fqn}
                            )
                            self.graph.add_edge(edge)
