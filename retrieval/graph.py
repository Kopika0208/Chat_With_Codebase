# graph.py
"""
Graph-aware retrieval using knowledge graph and call graph relationships.
"""

import os
import json
import streamlit as st
from pyvis.network import Network
import networkx as nx
from langchain_core.documents import Document

from cache import get_vectorstore, load_knowledge_graph_cached, load_symbol_table_cached, load_call_graph_cached


class GraphAwareRetriever:
    """Graph-aware retrieval that pulls related code using knowledge graph."""
    
    def __init__(self, vectorstore, knowledge_graph, symbol_table, call_graph):
        self.vectorstore = vectorstore
        self.kg = knowledge_graph
        self.symbol_table = symbol_table
        self.call_graph = call_graph
        
        # Build reverse indexes for fast lookup
        self._build_indexes()
    
    def _build_indexes(self):
        """Build lookup indexes from knowledge graph."""
        self.node_by_name = {}  # name -> [node_ids]
        self.edges_by_source = {}  # source_id -> [edges]
        self.edges_by_target = {}  # target_id -> [edges]
        
        # Index nodes
        for node_id, node_data in self.kg.get("nodes", {}).items():
            name = node_data.get("name", "")
            if name:
                if name not in self.node_by_name:
                    self.node_by_name[name] = []
                self.node_by_name[name].append(node_id)
        
        # Index edges
        for edge in self.kg.get("edges", []):
            src = edge.get("source")
            tgt = edge.get("target")
            
            if src not in self.edges_by_source:
                self.edges_by_source[src] = []
            self.edges_by_source[src].append(edge)
            
            if tgt not in self.edges_by_target:
                self.edges_by_target[tgt] = []
            self.edges_by_target[tgt].append(edge)
    
    def _get_kg_neighbors(self, node_id, edge_types=None):
        """Get all neighbors of a node in the knowledge graph."""
        neighbors = set()
        
        # Outgoing edges
        for edge in self.edges_by_source.get(node_id, []):
            if edge_types is None or edge.get("type") in edge_types:
                target = edge.get("target")
                if target:
                    neighbors.add(target)
        
        # Incoming edges
        for edge in self.edges_by_target.get(node_id, []):
            if edge_types is None or edge.get("type") in edge_types:
                source = edge.get("source")
                if source:
                    neighbors.add(source)
        
        return neighbors
    
    def _get_call_graph_neighbors(self, symbol_name):
        """Get functions called by or calling a symbol."""
        neighbors = set()
        
        for caller, callees in self.call_graph.items():
            # If this symbol is a caller, add all callees
            if symbol_name in caller:
                neighbors.update(callees)
            
            # If this symbol is a callee, add the caller
            for callee in callees:
                if symbol_name in callee:
                    neighbors.add(caller)
        
        return neighbors
    
    def _get_sibling_methods(self, node_id):
        """Get all sibling methods in the same class."""
        siblings = set()
        
        # Find sibling_method edges
        for edge in self.kg.get("edges", []):
            if edge.get("type") == "sibling_method":
                if edge.get("source") == node_id:
                    siblings.add(edge.get("target"))
                elif edge.get("target") == node_id:
                    siblings.add(edge.get("source"))
        
        return siblings
    
    def _get_entire_class(self, node_id):
        """Get all methods and properties of a class."""
        class_members = set()
        
        # Find contains_method edges where this is the class
        for edge in self.kg.get("edges", []):
            if edge.get("type") == "contains_method" and edge.get("source") == node_id:
                class_members.add(edge.get("target"))
        
        return class_members
    
    def _find_parent_class(self, node_id):
        """Find the parent class of a method."""
        # Look for contains_method edges where this is the target
        for edge in self.kg.get("edges", []):
            if edge.get("type") == "contains_method" and edge.get("target") == node_id:
                return edge.get("source")
        return None
    
    def retrieve_graph_aware(self, primary_chunk: Document, include_related: bool = True):
        """
        Retrieve a chunk and optionally its graph neighbors.
        
        Args:
            primary_chunk: The initial document chunk
            include_related: If True, expand to related chunks
        
        Returns:
            List of document chunks including primary and related
        """
        results = [primary_chunk]
        
        if not include_related:
            return results
        
        meta = primary_chunk.metadata or {}
        symbol_name = meta.get("symbol_name")
        file_path = meta.get("path")
        node_type = meta.get("node_type")
        
        if not symbol_name or not file_path:
            return results
        
        # Build node_id based on symbol name
        node_id = f"{file_path}:{symbol_name}"
        
        # Collect all related node IDs
        related_node_ids = set()
        
        # 1️⃣ Get knowledge graph neighbors (all edge types)
        kg_neighbors = self._get_kg_neighbors(node_id)
        related_node_ids.update(kg_neighbors)
        
        # 2️⃣ Get call graph neighbors
        call_neighbors = self._get_call_graph_neighbors(symbol_name)
        for neighbor in call_neighbors:
            # Extract symbol name from FQN
            if ":" in neighbor:
                related_node_ids.add(neighbor)
        
        # 3️⃣ Get sibling methods
        sibling_methods = self._get_sibling_methods(node_id)
        related_node_ids.update(sibling_methods)
        
        # 4️⃣ If this is a method, get entire class
        if node_type == "method":
            parent_class = self._find_parent_class(node_id)
            if parent_class:
                class_members = self._get_entire_class(parent_class)
                related_node_ids.update(class_members)
                related_node_ids.add(parent_class)
        
        # 5️⃣ If this is a class, get all its members
        if node_type == "class":
            class_members = self._get_entire_class(node_id)
            related_node_ids.update(class_members)
        
        # Convert node IDs back to chunks
        for related_node_id in related_node_ids:
            try:
                # Parse node_id to extract file and symbol
                parts = related_node_id.rsplit(":", 1)
                if len(parts) == 2:
                    rel_file, rel_symbol = parts
                    
                    # Search vectorstore for chunk matching this symbol
                    search_docs = self.vectorstore.similarity_search(rel_symbol, k=5)
                    for doc in search_docs:
                        doc_meta = doc.metadata or {}
                        if (doc_meta.get("path") == rel_file and 
                            doc_meta.get("symbol_name") == rel_symbol):
                            if doc not in results:
                                results.append(doc)
                            break
            except Exception:
                pass
        
        print(f"📚 Graph-aware retrieval: expanded {len([primary_chunk])} → {len(results)} chunks")
        return results
    
    def retrieve_with_expansion(self, initial_docs, max_expansion=10):
        """
        Retrieve initial docs and expand via graph relationships.
        
        Args:
            initial_docs: List of initial document chunks
            max_expansion: Maximum additional chunks to add
        
        Returns:
            Expanded list of document chunks
        """
        expanded = list(initial_docs)
        seen_symbols = set()
        
        for doc in initial_docs:
            meta = doc.metadata or {}
            symbol = meta.get("symbol_name")
            if symbol:
                seen_symbols.add(symbol)
        
        # For each initial doc, get related ones
        for doc in list(initial_docs):
            if len(expanded) >= len(initial_docs) + max_expansion:
                break
            
            related = self.retrieve_graph_aware(doc, include_related=True)
            for rel_doc in related:
                if rel_doc not in expanded:
                    rel_meta = rel_doc.metadata or {}
                    rel_symbol = rel_meta.get("symbol_name")
                    if rel_symbol not in seen_symbols:
                        expanded.append(rel_doc)
                        seen_symbols.add(rel_symbol)
                        if len(expanded) >= len(initial_docs) + max_expansion:
                            break
        
        return expanded[:len(initial_docs) + max_expansion]
    
    def retrieve_by_code_similarity(self, query_doc, k=10, similarity_types=None):
        """Retrieve chunks based on code structure similarity using unified retriever."""
        from cache import get_unified_retriever
        
        if similarity_types is None:
            similarity_types = ["signature", "control_flow", "imports", "api_calls"]
        
        # Get unified retriever
        retriever = get_unified_retriever()
        if not retriever:
            return []
        
        # Build weights based on requested similarity types
        weights = {
            "semantic": 0.25,
            "signature": 0.15 if "signature" in similarity_types else 0,
            "control_flow": 0.15 if "control_flow" in similarity_types else 0,
            "imports": 0.10 if "imports" in similarity_types else 0,
            "api_calls": 0.15 if "api_calls" in similarity_types else 0,
            "symbol": 0.10,
            "callgraph": 0.10,
        }
        
        # Normalize weights
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        results = retriever.retrieve_unified(
            query_doc.page_content,
            k=k,
            weights=weights
        )
        
        return results


@st.cache_resource(show_spinner=False)
def get_graph_aware_retriever():
    """Initialize graph-aware retriever."""
    try:
        vectorstore = get_vectorstore()
        kg = load_knowledge_graph_cached()
        st_data = load_symbol_table_cached()
        call_graph = load_call_graph_cached()
        
        if kg and call_graph:
            retriever = GraphAwareRetriever(vectorstore, kg, st_data, call_graph)
            print("✅ Graph-aware retriever initialized")
            return retriever
        else:
            print("⚠️ Knowledge graph or call graph not available for graph-aware retrieval")
            return None
    except Exception as e:
        print(f"⚠️ Failed to initialize graph-aware retriever: {e}")
        return None


@st.cache_data(show_spinner=False)
def build_call_graph_html(call_graph, focus_symbol=None, max_depth=2):
    """
    Build an interactive call graph HTML using PyVis.
    Cached so switching focus is cheap.
    """
    try:
        net = Network(height="650px", width="100%", directed=True)
        G = nx.DiGraph()

        # Build graph structure
        for caller, callees in call_graph.items():
            for callee in callees:
                G.add_edge(caller, callee)

        # Subgraph if focus is selected
        if focus_symbol and focus_symbol in G.nodes:
            nodes_to_show = {focus_symbol}
            frontier = {focus_symbol}
            for _ in range(max_depth):
                new_frontier = set()
                for node in frontier:
                    for neighbor in G.neighbors(node):
                        new_frontier.add(neighbor)
                    for pred in G.predecessors(node):
                        new_frontier.add(pred)
                nodes_to_show.update(new_frontier)
                frontier = new_frontier
            H = G.subgraph(nodes_to_show)
        else:
            H = G

        # Add nodes+edges to PyVis
        for node in H.nodes():
            net.add_node(node, label=node, title=node, color="#6EC1E4")

        for u, v in H.edges():
            net.add_edge(u, v, color="#999999")

        net.set_options(
            """
        const options = {
          "nodes": {
            "shape": "dot",
            "size": 16,
            "font": {"size": 14}
          },
          "edges": {
            "color": {"inherit": true},
            "arrows": {"to": {"enabled": true}},
            "smooth": false
          },
          "physics": {
            "enabled": true,
            "stabilization": {"iterations": 150}
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """
        )

        html = net.generate_html("callgraph.html")
        return html
    except Exception as e:
        return f"<p>Error rendering call graph: {e}</p>"


def render_call_graph(call_graph, focus_symbol=None, max_depth=2):
    """Render call graph in Streamlit."""
    import streamlit.components.v1 as components
    
    html_code = build_call_graph_html(call_graph, focus_symbol, max_depth)
    components.html(html_code, height=700, scrolling=True)
