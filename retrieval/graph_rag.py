"""
Graph-RAG Retrieval Pipeline

Implements the full Graph-RAG system:
1. Vector similarity search for anchor nodes
2. Knowledge graph traversal to expand context
3. Retrieval of code chunks for expanded nodes
4. Assembly of final context for LLM
"""

import os
from typing import List, Set, Dict, Optional
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
            meta = doc.metadata or {}
            path = meta.get("path", "")
            symbol = meta.get("symbol_name", "")
            if path and symbol:
                anchor_nodes.add(f"{path}:{symbol}")
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

            parts = node_id.split(":", 1)
            if len(parts) != 2:
                continue

            _, symbol_name = parts
            for doc in self.symbol_to_doc.get(symbol_name, []):
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


# ======================================================
# 🏭 FACTORY
# ======================================================
def create_graph_rag_retriever(
    vectorstore,
    knowledge_graph_path: str,
    documents: List[Document],
    repo_name: Optional[str] = None,
) -> GraphRAGRetriever:
    """
    Factory function to create a repo-scoped GraphRAGRetriever.
    """

    if not os.path.exists(knowledge_graph_path):
        raise FileNotFoundError(
            f"Knowledge graph not found: {knowledge_graph_path}"
        )

    print(f"[GraphRAG] Loading knowledge graph from {knowledge_graph_path}")
    graph = load_knowledge_graph(knowledge_graph_path)
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
