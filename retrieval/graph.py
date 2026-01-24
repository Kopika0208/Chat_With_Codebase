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

from cache import (
    get_vectorstore,
    load_knowledge_graph_cached,
    load_symbol_table_cached,
    load_call_graph_cached,
    get_unified_retriever,
)


class GraphAwareRetriever:
    """Graph-aware retrieval that pulls related code using knowledge graph."""

    def __init__(self, vectorstore, knowledge_graph, symbol_table, call_graph, repo_name):
        self.vectorstore = vectorstore
        self.kg = knowledge_graph
        self.symbol_table = symbol_table
        self.call_graph = call_graph
        self.repo_name = repo_name

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

        for edge in self.edges_by_source.get(node_id, []):
            if edge_types is None or edge.get("type") in edge_types:
                target = edge.get("target")
                if target:
                    neighbors.add(target)

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
            if symbol_name in caller:
                neighbors.update(callees)
            for callee in callees:
                if symbol_name in callee:
                    neighbors.add(caller)

        return neighbors

    def retrieve_graph_aware(self, primary_chunk: Document, include_related: bool = True):
        results = [primary_chunk]

        if not include_related:
            return results

        meta = primary_chunk.metadata or {}
        symbol_name = meta.get("symbol_name")
        file_path = meta.get("path")
        node_type = meta.get("node_type")

        if not symbol_name or not file_path:
            return results

        node_id = f"{file_path}:{symbol_name}"
        related_node_ids = set()

        related_node_ids.update(self._get_kg_neighbors(node_id))
        related_node_ids.update(self._get_call_graph_neighbors(symbol_name))

        for related_node_id in related_node_ids:
            try:
                parts = related_node_id.rsplit(":", 1)
                if len(parts) == 2:
                    rel_file, rel_symbol = parts

                    search_docs = self.vectorstore.similarity_search(rel_symbol, k=5)
                    for doc in search_docs:
                        doc_meta = doc.metadata or {}
                        if (
                            doc_meta.get("path") == rel_file
                            and doc_meta.get("symbol_name") == rel_symbol
                        ):
                            if doc not in results:
                                results.append(doc)
                            break
            except Exception:
                pass

        return results

    def retrieve_with_expansion(self, initial_docs, max_expansion=10):
        expanded = list(initial_docs)
        seen_symbols = set()

        for doc in initial_docs:
            meta = doc.metadata or {}
            symbol = meta.get("symbol_name")
            if symbol:
                seen_symbols.add(symbol)

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

        return expanded[: len(initial_docs) + max_expansion]

    def retrieve_by_code_similarity(self, query_doc, k=10, similarity_types=None):
        retriever = get_unified_retriever(self.repo_name)
        if not retriever:
            return []

        weights = {
            "semantic": 0.25,
            "signature": 0.15,
            "control_flow": 0.15,
            "imports": 0.10,
            "api_calls": 0.15,
            "symbol": 0.10,
            "callgraph": 0.10,
        }

        return retriever.retrieve_unified(
            query_doc.page_content,
            k=k,
            weights=weights,
        )


@st.cache_resource(show_spinner=False)
def get_graph_aware_retriever(repo_name: str):
    """Initialize graph-aware retriever."""
    try:
        vectorstore = get_vectorstore(repo_name)
        kg = load_knowledge_graph_cached(repo_name)
        st_data = load_symbol_table_cached(repo_name)
        call_graph = load_call_graph_cached(repo_name)

        if kg and call_graph:
            retriever = GraphAwareRetriever(
                vectorstore, kg, st_data, call_graph, repo_name
            )
            print(f"✅ Graph-aware retriever initialized for {repo_name}")
            return retriever
        else:
            print("⚠️ Knowledge graph or call graph not available")
            return None
    except Exception as e:
        print(f"⚠️ Failed to initialize graph-aware retriever: {e}")
        return None


@st.cache_data(show_spinner=False)
def build_call_graph_html(call_graph, focus_symbol=None, max_depth=2):
    net = Network(height="650px", width="100%", directed=True)
    G = nx.DiGraph()

    for caller, callees in call_graph.items():
        for callee in callees:
            G.add_edge(caller, callee)

    if focus_symbol and focus_symbol in G.nodes:
        nodes_to_show = {focus_symbol}
        frontier = {focus_symbol}
        for _ in range(max_depth):
            new_frontier = set()
            for node in frontier:
                new_frontier.update(G.neighbors(node))
                new_frontier.update(G.predecessors(node))
            nodes_to_show.update(new_frontier)
            frontier = new_frontier
        G = G.subgraph(nodes_to_show)

    for node in G.nodes():
        net.add_node(node, label=node, title=node)

    for u, v in G.edges():
        net.add_edge(u, v)

    return net.generate_html("callgraph.html")


def render_call_graph(call_graph, focus_symbol=None, max_depth=2):
    import streamlit.components.v1 as components

    html_code = build_call_graph_html(call_graph, focus_symbol, max_depth)
    components.html(html_code, height=700, scrolling=True)
