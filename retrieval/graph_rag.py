"""
Graph-RAG Retrieval Pipeline

Implements the full Graph-RAG system:
1. Vector similarity search for anchor nodes
2. Knowledge graph traversal to expand context
3. Retrieval of code chunks for expanded nodes
4. Assembly of final context for LLM
"""

import os
from collections import deque
from typing import List, Set, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from langchain_core.documents import Document

try:
    from .graph_traversal import (
        GraphTraversal,
        TraversalStrategy,
        TraversalResult,
        load_knowledge_graph,
    )
except ImportError:
    from graph_traversal import (
        GraphTraversal,
        TraversalStrategy,
        TraversalResult,
        load_knowledge_graph,
    )


# ======================================================
# 📦 RESULT OBJECT
# ======================================================
@dataclass
class GraphRAGResult:
    """Result of a Graph-RAG retrieval."""
    query: str
    anchor_documents: List[Document]
    anchor_nodes: Set[str]
    expansion_result: TraversalResult
    expanded_documents: List[Document]
    final_documents: List[Document]
    statistics: Dict

    def summary(self) -> str:
        return f"""
Graph-RAG Retrieval Summary:
  Query: {self.query!r}
  Anchor documents: {len(self.anchor_documents)}
  Anchor nodes: {len(self.anchor_nodes)}
  Graph expansion depth: {
      max(self.expansion_result.reached_nodes_by_depth.keys())
      if self.expansion_result.reached_nodes_by_depth else 0
  }
  Total nodes visited: {len(self.expansion_result.visited_nodes)}
  Final documents: {len(self.final_documents)}
  Edge types traversed: {
      len(set(et for _, _, et in self.expansion_result.edges_traversed))
  }
"""


# ======================================================
# 🔗 GRAPH-RAG RETRIEVER
# ======================================================
class GraphRAGRetriever:
    """
    Graph-RAG retrieval system combining vector search and knowledge graph.

    Multi-repo safe: all repo-specific state is injected explicitly.
    """

    def __init__(
        self,
        vectorstore,
        graph_traversal: GraphTraversal,
        documents: List[Document],
        chunk_by_symbol: Dict[str, List[Document]],
        repo_name: Optional[str] = None,
    ):
        self.vectorstore = vectorstore
        self.graph = graph_traversal
        self.documents = documents
        self.chunk_by_symbol = chunk_by_symbol
        self.repo_name = repo_name  # for debugging / clarity only

        # Build symbol → documents index
        self.symbol_to_doc: Dict[str, List[Document]] = {}
        for doc in documents:
            meta = doc.metadata or {}
            symbol_name = meta.get("symbol_name")
            if symbol_name:
                self.symbol_to_doc.setdefault(symbol_name, []).append(doc)

        self.graph_nodes_by_file_and_name: Dict[Tuple[str, str], List[Tuple[str, Dict]]] = {}
        for node_id, node in self.graph.nodes.items():
            file_path = str(node.get("file", "") or "")
            name = str(node.get("name", "") or "")
            if file_path and name:
                self.graph_nodes_by_file_and_name.setdefault((file_path, name), []).append((node_id, node))

        self.doc_to_graph_nodes: Dict[str, Set[str]] = {}
        self.graph_node_to_docs: Dict[str, List[Document]] = {}
        for doc in documents:
            resolved_node_ids = self._resolve_graph_nodes_for_doc(doc)
            if not resolved_node_ids:
                continue

            doc_id = self._doc_id(doc)
            self.doc_to_graph_nodes[doc_id] = resolved_node_ids
            for node_id in resolved_node_ids:
                self.graph_node_to_docs.setdefault(node_id, []).append(doc)

    # ==================================================
    # 🚀 MAIN RETRIEVAL
    # ==================================================
    def retrieve(
        self,
        query: str,
        k_initial: int = 5,
        max_depth: int = 2,
        strategy: str = "bfs",
        edge_types: Optional[List[str]] = None,
        deduplicate: bool = True,
    ) -> GraphRAGResult:

        # 1️⃣ Vector search
        anchor_documents = self._vector_search(query, k_initial)

        # 2️⃣ Anchor nodes
        anchor_nodes = self._extract_anchor_nodes(anchor_documents)

        # 3️⃣ Graph traversal
        strategy_enum = (
            TraversalStrategy.BFS if strategy == "bfs" else TraversalStrategy.DFS
        )

        expansion_result = self.graph.traverse(
            anchor_nodes=anchor_nodes,
            max_depth=max_depth,
            strategy=strategy_enum,
            edge_types=edge_types,
            direction="both",
        )

        # 4️⃣ Expanded docs
        expanded_documents = self._retrieve_documents_for_nodes(
            expansion_result.visited_nodes,
            exclude_nodes=anchor_nodes,
        )

        # 5️⃣ Combine + dedupe
        final_documents = anchor_documents + expanded_documents
        if deduplicate:
            final_documents = self._deduplicate_documents(final_documents)

        statistics = {
            "initial_vector_results": len(anchor_documents),
            "anchor_nodes": len(anchor_nodes),
            "expanded_nodes": max(0, len(expansion_result.visited_nodes) - len(anchor_nodes)),
            "total_nodes_visited": len(expansion_result.visited_nodes),
            "edges_traversed": len(expansion_result.edges_traversed),
            "max_depth_reached": max(
                expansion_result.reached_nodes_by_depth.keys()
            ) if expansion_result.reached_nodes_by_depth else 0,
            "final_document_count": len(final_documents),
        }

        return GraphRAGResult(
            query=query,
            anchor_documents=anchor_documents,
            anchor_nodes=anchor_nodes,
            expansion_result=expansion_result,
            expanded_documents=expanded_documents,
            final_documents=final_documents,
            statistics=statistics,
        )

    # ==================================================
    # 🔍 INTERNAL HELPERS
    # ==================================================
    def _vector_search(self, query: str, k: int) -> List[Document]:
        try:
            return self.vectorstore.similarity_search(query, k=k)
        except Exception as e:
            print(f"⚠️ Vector search error: {e}")
            return []

    def _extract_anchor_nodes(self, documents: List[Document]) -> Set[str]:
        anchor_nodes = set()
        for doc in documents:
            doc_id = self._doc_id(doc)
            anchor_nodes.update(self.doc_to_graph_nodes.get(doc_id, set()))
        return anchor_nodes

    def _retrieve_documents_for_nodes(
        self,
        node_ids: Set[str],
        exclude_nodes: Optional[Set[str]] = None,
    ) -> List[Document]:
        exclude_nodes = exclude_nodes or set()
        documents = []
        seen = set()

        for node_id in node_ids:
            if node_id in exclude_nodes:
                continue
            for doc in self.graph_node_to_docs.get(node_id, []):
                doc_id = self._doc_id(doc)
                if doc_id not in seen:
                    seen.add(doc_id)
                    documents.append(doc)

        return documents

    def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        seen = set()
        deduped = []
        for doc in documents:
            doc_id = self._doc_id(doc)
            if doc_id not in seen:
                seen.add(doc_id)
                deduped.append(doc)
        return deduped

    @staticmethod
    def _doc_id(doc: Document) -> str:
        meta = doc.metadata or {}
        return f"{meta.get('path','')}:{meta.get('start_line',0)}"

    def _resolve_graph_nodes_for_doc(self, doc: Document) -> Set[str]:
        """Resolve a retrieved chunk to KG node ids using file/name/line metadata."""
        meta = doc.metadata or {}
        file_path = str(meta.get("path", "") or "")
        symbol_name = str(meta.get("symbol_name", "") or "")
        if not file_path or not symbol_name:
            return set()

        exact_node_id = f"{file_path}:{symbol_name}"
        if exact_node_id in self.graph.nodes:
            return {exact_node_id}

        candidates = list(self.graph_nodes_by_file_and_name.get((file_path, symbol_name), []))
        if not candidates:
            normalized_file = file_path.replace("\\", "/")
            for (candidate_file, candidate_name), matches in self.graph_nodes_by_file_and_name.items():
                if candidate_name != symbol_name:
                    continue
                if candidate_file.replace("\\", "/") == normalized_file:
                    candidates.extend(matches)

        if not candidates:
            return set()

        start_line = int(meta.get("start_line", 0) or 0)
        end_line = int(meta.get("end_line", start_line) or start_line)
        parent_class = str(meta.get("parent_class", "") or "")

        def score(candidate: Tuple[str, Dict]) -> Tuple[int, int]:
            node_id, node = candidate
            node_line = int(node.get("line", 0) or 0)

            class_penalty = 0
            if parent_class and f":{parent_class}:" not in node_id:
                class_penalty = 1

            line_distance = 0
            if start_line and node_line:
                if start_line <= node_line <= max(start_line, end_line):
                    line_distance = 0
                else:
                    line_distance = min(abs(node_line - start_line), abs(node_line - end_line))

            return (class_penalty, line_distance)

        best_node_id, _ = min(candidates, key=score)
        return {best_node_id}

    def trace_request_path(
        self,
        entry_symbol: str,
        target_symbol: Optional[str] = None,
        max_depth: int = 8,
    ) -> Dict[str, object]:
        """Trace a likely request/dataflow path from entry code toward downstream logic."""
        entry_node = self._resolve_symbol_node(entry_symbol)
        target_node = self._resolve_symbol_node(target_symbol) if target_symbol else None

        if not entry_node:
            return {
                "entry_node": None,
                "target_node": target_node,
                "path": [],
                "documents": [],
                "summary": f"Could not resolve entry symbol '{entry_symbol}' in the knowledge graph.",
            }

        path_edges = self._find_preferred_path(entry_node, target_node, max_depth=max_depth)
        path_nodes = [entry_node]
        for source_id, target_id, edge_type, props in path_edges:
            if not path_nodes or path_nodes[-1] != source_id:
                path_nodes.append(source_id)
            if path_nodes[-1] != target_id:
                path_nodes.append(target_id)

        documents = self._retrieve_documents_for_nodes(set(path_nodes))
        steps = []
        for idx, node_id in enumerate(path_nodes):
            node = self.graph.nodes.get(node_id, {})
            inbound = None
            if idx > 0 and idx - 1 < len(path_edges):
                inbound = path_edges[idx - 1]
            steps.append({
                "node_id": node_id,
                "name": node.get("name", node_id),
                "type": node.get("type", "unknown"),
                "file": node.get("file", ""),
                "line": node.get("line", 0),
                "incoming_edge_type": inbound[2] if inbound else None,
                "incoming_edge_properties": inbound[3] if inbound else {},
            })

        return {
            "entry_node": entry_node,
            "target_node": target_node,
            "path": steps,
            "documents": documents,
            "summary": (
                f"Traced {len(steps)} step(s) from {entry_symbol}"
                + (f" toward {target_symbol}." if target_symbol else ".")
            ),
        }

    def _resolve_symbol_node(self, symbol: Optional[str]) -> Optional[str]:
        """Resolve a user-facing symbol or FQN to a knowledge-graph node id."""
        if not symbol:
            return None
        if symbol in self.graph.nodes:
            return symbol

        normalized = symbol.lower()
        exact_matches = []
        suffix_matches = []
        name_matches = []
        for node_id, node in self.graph.nodes.items():
            node_name = str(node.get("name", "")).lower()
            if node_id.lower() == normalized:
                exact_matches.append(node_id)
            elif node_id.lower().endswith(f":{normalized}"):
                suffix_matches.append(node_id)
            elif node_name == normalized:
                name_matches.append(node_id)

        for matches in (exact_matches, suffix_matches, name_matches):
            if matches:
                return matches[0]
        return None

    def _find_preferred_path(
        self,
        entry_node: str,
        target_node: Optional[str],
        max_depth: int = 8,
    ) -> List[Tuple[str, str, str, Dict]]:
        """Find a forward path preferring dataflow edges, then calls, then containment."""
        preferred_edges = ["dataflow", "calls", "contains"]
        queue = deque([(entry_node, [], 0)])
        visited = {entry_node}

        best_path = []
        best_score = -1

        while queue:
            current, path, depth = queue.popleft()
            if depth >= max_depth:
                continue

            if target_node and current == target_node:
                return path

            neighbors = self.graph.adjacency_out.get(current, [])
            ranked_neighbors = sorted(
                neighbors,
                key=lambda item: (
                    preferred_edges.index(item[1]) if item[1] in preferred_edges else len(preferred_edges),
                    0 if self._looks_like_downstream_target(item[0]) else 1,
                )
            )

            for neighbor_id, edge_type, props in ranked_neighbors:
                if neighbor_id in visited:
                    continue
                next_path = path + [(current, neighbor_id, edge_type, props)]
                score = self._path_score(next_path)
                if not target_node and score > best_score:
                    best_score = score
                    best_path = next_path
                visited.add(neighbor_id)
                queue.append((neighbor_id, next_path, depth + 1))

        return best_path

    def _path_score(self, path: List[Tuple[str, str, str, Dict]]) -> int:
        """Score a path based on dataflow richness and downstream-looking nodes."""
        score = 0
        for _, target_id, edge_type, props in path:
            if edge_type == "dataflow":
                score += 3
                if props.get("flow_kind") == "interprocedural_call":
                    score += 2
                if props.get("flow_kind") == "return_propagation":
                    score += 1
            elif edge_type == "calls":
                score += 2
            elif edge_type == "contains":
                score += 1

            if self._looks_like_downstream_target(target_id):
                score += 2
        return score

    def _looks_like_downstream_target(self, node_id: str) -> bool:
        """Heuristic for service/repository/data-access style endpoints."""
        node = self.graph.nodes.get(node_id, {})
        text = " ".join(
            [
                str(node_id).lower(),
                str(node.get("name", "")).lower(),
                str(node.get("file", "")).lower(),
            ]
        )
        return any(token in text for token in ("repo", "repository", "dao", "db", "database", "model", "query", "save", "fetch", "store"))


# ======================================================
# 🏭 FACTORY
# ======================================================
def create_graph_rag_retriever(
    vectorstore,
    knowledge_graph_source: Union[str, dict],
    documents: List[Document],
    repo_name: Optional[str] = None,
) -> GraphRAGRetriever:
    """
    Factory function to create a repo-scoped GraphRAGRetriever.
    """

    if isinstance(knowledge_graph_source, str) and not os.path.exists(knowledge_graph_source):
        raise FileNotFoundError(
            f"Knowledge graph not found: {knowledge_graph_source}"
        )

    print(f"[GraphRAG] Loading knowledge graph")
    graph = load_knowledge_graph(knowledge_graph_source)
    print(f"[GraphRAG] ✓ Loaded KG with {len(graph.nodes)} nodes")

    # Build symbol → documents map
    chunk_by_symbol: Dict[str, List[Document]] = {}
    for doc in documents:
        symbol = (doc.metadata or {}).get("symbol_name")
        if symbol:
            chunk_by_symbol.setdefault(symbol, []).append(doc)

    print(f"[GraphRAG] ✓ Built symbol map with {len(chunk_by_symbol)} symbols")

    return GraphRAGRetriever(
        vectorstore=vectorstore,
        graph_traversal=graph,
        documents=documents,
        chunk_by_symbol=chunk_by_symbol,
        repo_name=repo_name,
    )
