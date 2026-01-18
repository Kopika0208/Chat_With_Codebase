# knowledge_graph.py - Knowledge graph builder and related classes

import ast
import re
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
from .symbols import Symbol, SymbolTable


@dataclass
class KnowledgeGraphNode:
    """Represents a node in the knowledge graph."""
    node_id: str  # unique identifier
    node_type: str  # "function", "class", "method", "variable", "return_value", "parameter", "import"
    name: str
    file_path: str
    line_number: int
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.node_id)
    
    def __eq__(self, other):
        if isinstance(other, KnowledgeGraphNode):
            return self.node_id == other.node_id
        return False


@dataclass
class KnowledgeGraphEdge:
    """Represents an edge in the knowledge graph."""
    source_id: str
    target_id: str
    edge_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash((self.source_id, self.target_id, self.edge_type))
    
    def __eq__(self, other):
        if isinstance(other, KnowledgeGraphEdge):
            return (self.source_id == other.source_id and
                    self.target_id == other.target_id and
                    self.edge_type == other.edge_type)
        return False


class KnowledgeGraph:
    """Comprehensive knowledge graph for codebase understanding."""
    
    def __init__(self):
        self.nodes: Dict[str, KnowledgeGraphNode] = {}
        self.edges: Set[KnowledgeGraphEdge] = set()
        self.adjacency: Dict[str, List[KnowledgeGraphEdge]] = defaultdict(list)
    
    def add_node(self, node: KnowledgeGraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
    
    def add_edge(self, edge: KnowledgeGraphEdge) -> None:
        """Add an edge to the graph."""
        if edge not in self.edges:
            self.edges.add(edge)
            self.adjacency[edge.source_id].append(edge)
    
    def get_node(self, node_id: str) -> Optional[KnowledgeGraphNode]:
        """Retrieve a node by ID."""
        return self.nodes.get(node_id)
    
    def get_outgoing_edges(self, node_id: str, edge_type: str = None) -> List[KnowledgeGraphEdge]:
        """Get all outgoing edges from a node, optionally filtered by type."""
        edges = self.adjacency.get(node_id, [])
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges
    
    def get_incoming_edges(self, node_id: str, edge_type: str = None) -> List[KnowledgeGraphEdge]:
        """Get all incoming edges to a node, optionally filtered by type."""
        edges = [e for e in self.edges if e.target_id == node_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export graph as dictionary for JSON serialization."""
        return {
            "nodes": {
                node_id: {
                    "type": node.node_type,
                    "name": node.name,
                    "file": node.file_path,
                    "line": node.line_number,
                    "properties": node.properties,
                }
                for node_id, node in self.nodes.items()
            },
            "edges": [
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type,
                    "properties": edge.properties,
                }
                for edge in self.edges
            ],
        }


class KnowledgeGraphBuilder:
    """Build comprehensive knowledge graph from symbol table and data flow analysis."""
    
    def __init__(self):
        self.graph = KnowledgeGraph()
        self.class_hierarchy: Dict[str, List[str]] = {}
        self.method_map: Dict[str, Dict[str, str]] = {}
        self.test_methods: Dict[str, str] = {}
    
    def build_from_symbols(self, symbol_tables: Dict[str, SymbolTable]) -> None:
        """Build graph from symbol tables."""
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
                        "docstring": symbol.docstring,
                        "parent_symbol": symbol.parent_symbol,
                    }
                )
                self.graph.add_node(node)
        
        # Second pass: add edges
        for file_path, symbol_table in symbol_tables.items():
            for fqn, symbol in symbol_table.all_symbols.items():
                self._build_symbol_edges(symbol, symbol_table, file_path)
    
    def build_from_dataflow(self, dataflow_by_file: Dict[str, Dict[str, Any]]) -> None:
        """Build graph from data flow analysis."""
        for file_path, functions in dataflow_by_file.items():
            for func_name, analysis in functions.items():
                # Add return value node
                return_node_id = f"{file_path}:{func_name}:return"
                return_node = KnowledgeGraphNode(
                    node_id=return_node_id,
                    node_type="return_value",
                    name=f"return_{func_name}",
                    file_path=file_path,
                    line_number=analysis.get("line", 0),
                    properties={"function": func_name}
                )
                self.graph.add_node(return_node)
                
                # Add definition and use relationships
                for var_name, defs in analysis.get("definitions", {}).items():
                    for defn in defs:
                        def_node_id = f"{file_path}:{func_name}:{var_name}@{defn['line']}"
                        def_node = KnowledgeGraphNode(
                            node_id=def_node_id,
                            node_type="definition",
                            name=var_name,
                            file_path=file_path,
                            line_number=defn["line"],
                            properties={
                                "inferred_type": defn.get("type"),
                                "constant_value": defn.get("constant"),
                                "is_parameter": defn.get("is_param", False),
                            }
                        )
                        self.graph.add_node(def_node)
                
                # Add def-use chain edges
                for chain_id, chain_data in analysis.get("def_use_chains", {}).items():
                    parts = chain_id.split("@")
                    var_name = parts[0]
                    def_line = int(parts[1]) if len(parts) > 1 else 0
                    
                    def_node_id = f"{file_path}:{func_name}:{var_name}@{def_line}"
                    
                    for use in chain_data.get("uses", []):
                        use_node_id = f"{file_path}:{func_name}:{var_name}_use@{use['line']}"
                        use_node = KnowledgeGraphNode(
                            node_id=use_node_id,
                            node_type="use",
                            name=f"{var_name}_use",
                            file_path=file_path,
                            line_number=use["line"],
                            properties={"context": use.get("context", "unknown")}
                        )
                        self.graph.add_node(use_node)
                        
                        # Add flow edge
                        edge = KnowledgeGraphEdge(
                            source_id=def_node_id,
                            target_id=use_node_id,
                            edge_type="flow",
                            properties={
                                "variable": var_name,
                                "flow_type": "def_use",
                            }
                        )
                        self.graph.add_edge(edge)
    
    def _build_symbol_edges(self, symbol: Symbol, symbol_table: SymbolTable, file_path: str) -> None:
        """Build edges for a symbol."""
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
        
        # Import edges
        if symbol.kind == "import":
            edge = KnowledgeGraphEdge(
                source_id=fqn,
                target_id=symbol.docstring or "external",
                edge_type="imports",
                properties={"module": symbol.docstring}
            )
            self.graph.add_edge(edge)
        
        # Docstring relationship
        if symbol.docstring and symbol.kind in ("function", "method", "class"):
            doc_node_id = f"{file_path}:{symbol.name}:docstring"
            if doc_node_id not in self.graph.nodes:
                doc_node = KnowledgeGraphNode(
                    node_id=doc_node_id,
                    node_type="docstring",
                    name=f"doc_{symbol.name}",
                    file_path=file_path,
                    line_number=symbol.line_number,
                    properties={"content": symbol.docstring[:200]}
                )
                self.graph.add_node(doc_node)
            
            edge = KnowledgeGraphEdge(
                source_id=doc_node_id,
                target_id=fqn,
                edge_type="documents",
                properties={"documentation_type": "docstring"}
            )
            self.graph.add_edge(edge)
        
        # Parent-child relationship (method in class)
        if symbol.parent_symbol and ":" in symbol.parent_symbol:
            parent_fqn = symbol.parent_symbol
            if parent_fqn in self.graph.nodes:
                edge = KnowledgeGraphEdge(
                    source_id=parent_fqn,
                    target_id=fqn,
                    edge_type="contains_method",
                    properties={"member_type": symbol.kind}
                )
                self.graph.add_edge(edge)
    
    def add_call_graph_edges(self, call_graph: Dict[str, List[str]]) -> None:
        """Add call graph as edges to the knowledge graph."""
        for caller_fqn, callees in call_graph.items():
            for callee_fqn in callees:
                # Ensure nodes exist
                if caller_fqn in self.graph.nodes and callee_fqn in self.graph.nodes:
                    edge = KnowledgeGraphEdge(
                        source_id=caller_fqn,
                        target_id=callee_fqn,
                        edge_type="calls"
                    )
                    self.graph.add_edge(edge)
    
    def add_attribute_access_edges(self, symbol_tables: Dict[str, SymbolTable]) -> None:
        """Add attribute access edges from source code analysis."""
        for file_path, symbol_table in symbol_tables.items():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    source_code = f.read()
                
                tree = ast.parse(source_code)
                
                class AttributeVisitor(ast.NodeVisitor):
                    def __init__(self, builder, file_path):
                        self.builder = builder
                        self.file_path = file_path
                        self.current_context = None
                    
                    def visit_FunctionDef(self, node):
                        old_context = self.current_context
                        self.current_context = f"{file_path}:{node.name}"
                        self.generic_visit(node)
                        self.current_context = old_context
                    
                    def visit_AsyncFunctionDef(self, node):
                        old_context = self.current_context
                        self.current_context = f"{file_path}:{node.name}"
                        self.generic_visit(node)
                        self.current_context = old_context
                    
                    def visit_Attribute(self, node):
                        # obj.attr access
                        if isinstance(node.value, ast.Name) and self.current_context:
                            obj_name = node.value.id
                            attr_name = node.attr
                            
                            # Try to find the attribute in the graph
                            attr_node_id = f"{self.file_path}:{attr_name}"
                            
                            if self.current_context in self.builder.graph.nodes and attr_node_id in self.builder.graph.nodes:
                                edge = KnowledgeGraphEdge(
                                    source_id=self.current_context,
                                    target_id=attr_node_id,
                                    edge_type="accesses_attribute",
                                    properties={
                                        "object": obj_name,
                                        "attribute": attr_name,
                                        "line": node.lineno,
                                    }
                                )
                                self.builder.graph.add_edge(edge)
                        
                        self.generic_visit(node)
                
                visitor = AttributeVisitor(self, file_path)
                visitor.visit(tree)
            except Exception as e:
                print(f"⚠️ Attribute access extraction failed for {file_path}: {e}")
    
    def add_test_relationships(self, symbol_tables: Dict[str, SymbolTable]) -> None:
        """Identify test methods and link them to tested functions."""
        test_pattern = re.compile(r'^test_', re.IGNORECASE)
        
        for file_path, symbol_table in symbol_tables.items():
            for fqn, symbol in symbol_table.all_symbols.items():
                if symbol.kind == "function" and test_pattern.match(symbol.name):
                    # This is a test function
                    func_name = symbol.name[5:] if symbol.name.startswith("test_") else symbol.name
                    
                    # Search for the function being tested
                    for candidate_fqn, candidate_symbol in symbol_table.all_symbols.items():
                        if candidate_symbol.kind in ("function", "method") and candidate_symbol.name == func_name:
                            edge = KnowledgeGraphEdge(
                                source_id=fqn,
                                target_id=candidate_fqn,
                                edge_type="tests",
                                properties={"test_type": "unit_test"}
                            )
                            self.graph.add_edge(edge)
    
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
