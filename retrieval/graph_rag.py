"""
Graph-RAG Retrieval Pipeline

Implements the full Graph-RAG system:
1. Vector similarity search for anchor nodes
2. Knowledge graph traversal to expand context
3. Retrieval of code chunks for expanded nodes
4. Assembly of final context for LLM
"""

import os
import json
from typing import List, Set, Dict, Optional, Tuple
from dataclasses import dataclass
from langchain_core.documents import Document

try:
    from .graph_traversal import GraphTraversal, TraversalStrategy, TraversalResult, load_knowledge_graph
except ImportError:
    from graph_traversal import GraphTraversal, TraversalStrategy, TraversalResult, load_knowledge_graph


@dataclass
class GraphRAGResult:
    """Result of a Graph-RAG retrieval."""
    query: str
    anchor_documents: List[Document]  # Initial vector search results
    anchor_nodes: Set[str]  # Extracted anchor node IDs
    expansion_result: TraversalResult  # Graph traversal result
    expanded_documents: List[Document]  # Documents from expanded nodes
    final_documents: List[Document]  # Deduplicated final documents
    statistics: Dict  # Statistics about retrieval
    
    def summary(self) -> str:
        """Get a human-readable summary."""
        return f"""
Graph-RAG Retrieval Summary:
  Query: {self.query!r}
  Anchor documents: {len(self.anchor_documents)}
  Anchor nodes: {len(self.anchor_nodes)}
  Graph expansion depth: {max(self.expansion_result.reached_nodes_by_depth.keys()) if self.expansion_result.reached_nodes_by_depth else 0}
  Total nodes visited: {len(self.expansion_result.visited_nodes)}
  Final documents: {len(self.final_documents)}
  Edge types traversed: {len(set(et for _, _, et in self.expansion_result.edges_traversed))}
"""


class GraphRAGRetriever:
    """Graph-RAG retrieval system combining vector search and knowledge graph.
    
    Workflow:
    1. Perform vector similarity search for initial (anchor) documents
    2. Extract symbol/node IDs from document metadata
    3. Traverse knowledge graph from anchor nodes (BFS/DFS)
    4. Collect code chunks for all reached nodes
    5. Return expanded context to LLM
    """
    
    def __init__(
        self,
        vectorstore,
        graph_traversal: GraphTraversal,
        documents: List[Document],
        chunk_by_symbol: Dict[str, List[Document]]
    ):
        """Initialize Graph-RAG retriever.
        
        Args:
            vectorstore: FAISS vectorstore for semantic search
            graph_traversal: GraphTraversal engine
            documents: All indexed documents
            chunk_by_symbol: Map from symbol_name -> list of Document chunks
        """
        self.vectorstore = vectorstore
        self.graph = graph_traversal
        self.documents = documents
        self.chunk_by_symbol = chunk_by_symbol
        
        # Build index: symbol_name -> document
        self.symbol_to_doc = {}
        for doc in documents:
            meta = doc.metadata or {}
            symbol_name = meta.get("symbol_name")
            if symbol_name:
                if symbol_name not in self.symbol_to_doc:
                    self.symbol_to_doc[symbol_name] = []
                self.symbol_to_doc[symbol_name].append(doc)
    
    def retrieve(
        self,
        query: str,
        k_initial: int = 5,
        max_depth: int = 2,
        strategy: str = "bfs",
        edge_types: Optional[List[str]] = None,
        deduplicate: bool = True
    ) -> GraphRAGResult:
        """Perform Graph-RAG retrieval.
        
        Args:
            query: User query
            k_initial: Number of initial vector search results
            max_depth: Maximum traversal depth in knowledge graph
            strategy: "bfs" or "dfs"
            edge_types: Filter graph traversal by edge types
            deduplicate: Whether to deduplicate final documents
        
        Returns:
            GraphRAGResult with all retrieval information
        """
        # Step 1: Vector similarity search for anchor documents
        anchor_documents = self._vector_search(query, k=k_initial)
        
        # Step 2: Extract anchor nodes from document metadata
        anchor_nodes = self._extract_anchor_nodes(anchor_documents)
        
        # Step 3: Traverse knowledge graph from anchor nodes
        strategy_enum = TraversalStrategy.BFS if strategy == "bfs" else TraversalStrategy.DFS
        expansion_result = self.graph.traverse(
            anchor_nodes=anchor_nodes,
            max_depth=max_depth,
            strategy=strategy_enum,
            edge_types=edge_types,
            direction="both"
        )
        
        # Step 4: Retrieve documents for expanded nodes
        expanded_documents = self._retrieve_documents_for_nodes(
            expansion_result.visited_nodes,
            exclude_nodes=anchor_nodes
        )
        
        # Step 5: Combine and deduplicate
        final_documents = anchor_documents + expanded_documents
        if deduplicate:
            final_documents = self._deduplicate_documents(final_documents)
        
        # Build statistics
        statistics = {
            "initial_vector_results": len(anchor_documents),
            "anchor_nodes": len(anchor_nodes),
            "total_nodes_visited": len(expansion_result.visited_nodes),
            "edges_traversed": len(expansion_result.edges_traversed),
            "max_depth_reached": max(expansion_result.reached_nodes_by_depth.keys()) if expansion_result.reached_nodes_by_depth else 0,
            "final_document_count": len(final_documents),
        }
        
        return GraphRAGResult(
            query=query,
            anchor_documents=anchor_documents,
            anchor_nodes=anchor_nodes,
            expansion_result=expansion_result,
            expanded_documents=expanded_documents,
            final_documents=final_documents,
            statistics=statistics
        )
    
    def _vector_search(self, query: str, k: int) -> List[Document]:
        """Perform vector similarity search.
        
        Args:
            query: Query string
            k: Number of results to retrieve
        
        Returns:
            List of Document objects
        """
        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return results
        except Exception as e:
            print(f"⚠️ Vector search error: {e}")
            return []
    
    def _extract_anchor_nodes(self, documents: List[Document]) -> Set[str]:
        """Extract knowledge graph node IDs from document metadata.
        
        Node IDs should be in format: file.py:symbol_name
        
        Args:
            documents: List of retrieved documents
        
        Returns:
            Set of node IDs
        """
        anchor_nodes = set()
        
        for doc in documents:
            meta = doc.metadata or {}
            path = meta.get("path", "")
            symbol_name = meta.get("symbol_name", "")
            
            if path and symbol_name:
                node_id = f"{path}:{symbol_name}"
                anchor_nodes.add(node_id)
        
        return anchor_nodes
    
    def _retrieve_documents_for_nodes(
        self,
        node_ids: Set[str],
        exclude_nodes: Optional[Set[str]] = None
    ) -> List[Document]:
        """Retrieve documents for given knowledge graph nodes.
        
        Args:
            node_ids: Knowledge graph node IDs
            exclude_nodes: Node IDs to exclude (e.g., anchor nodes)
        
        Returns:
            List of Document objects
        """
        if exclude_nodes is None:
            exclude_nodes = set()
        
        documents = []
        seen = set()
        
        for node_id in node_ids:
            if node_id in exclude_nodes:
                continue
            
            # Parse node_id: file.py:symbol_name
            parts = node_id.split(":", 1)
            if len(parts) != 2:
                continue
            
            file_path, symbol_name = parts
            
            # Look up documents by symbol name
            if symbol_name in self.symbol_to_doc:
                for doc in self.symbol_to_doc[symbol_name]:
                    doc_id = self._doc_id(doc)
                    if doc_id not in seen:
                        documents.append(doc)
                        seen.add(doc_id)
        
        return documents
    
    def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """Remove duplicate documents, keeping first occurrence.
        
        Args:
            documents: List of Document objects
        
        Returns:
            Deduplicated list
        """
        seen = set()
        deduplicated = []
        
        for doc in documents:
            doc_id = self._doc_id(doc)
            if doc_id not in seen:
                deduplicated.append(doc)
                seen.add(doc_id)
        
        return deduplicated
    
    @staticmethod
    def _doc_id(doc: Document) -> str:
        """Generate unique ID for a document."""
        meta = doc.metadata or {}
        path = meta.get("path", "")
        start_line = meta.get("start_line", 0)
        return f"{path}:{start_line}"
    
    def retrieve_with_debug(
        self,
        query: str,
        k_initial: int = 5,
        max_depth: int = 2,
        strategy: str = "bfs"
    ) -> GraphRAGResult:
        """Perform retrieval with debug output.
        
        Args:
            query: User query
            k_initial: Initial results
            max_depth: Traversal depth
            strategy: BFS or DFS
        
        Returns:
            GraphRAGResult with debug information
        """
        print(f"\n🔍 Graph-RAG Retrieval: {query!r}")
        print(f"   k_initial={k_initial}, max_depth={max_depth}, strategy={strategy}")
        
        result = self.retrieve(query, k_initial, max_depth, strategy)
        
        print(result.summary())
        print(f"   Anchor nodes: {result.anchor_nodes}")
        print(f"   Nodes by depth:")
        for depth, nodes in sorted(result.expansion_result.reached_nodes_by_depth.items()):
            print(f"      Depth {depth}: {len(nodes)} nodes")
        
        return result


def create_graph_rag_retriever(
    vectorstore,
    knowledge_graph_path: str,
    documents: List[Document]
) -> GraphRAGRetriever:
    """Factory function to create GraphRAGRetriever.
    
    Args:
        vectorstore: FAISS vectorstore
        knowledge_graph_path: Path to knowledge_graph.json
        documents: All indexed documents
    
    Returns:
        Configured GraphRAGRetriever instance
    """
    # Load knowledge graph
    if not os.path.exists(knowledge_graph_path):
        raise FileNotFoundError(f"Knowledge graph not found: {knowledge_graph_path}")
    
    print(f"[GraphRAG] Loading knowledge graph from: {knowledge_graph_path}")
    graph = load_knowledge_graph(knowledge_graph_path)
    print(f"[GraphRAG] ✓ Knowledge graph loaded with {len(graph.nodes)} nodes")
    
    # Build symbol-to-documents map
    chunk_by_symbol = {}
    for doc in documents:
        meta = doc.metadata or {}
        symbol = meta.get("symbol_name")
        if symbol:
            if symbol not in chunk_by_symbol:
                chunk_by_symbol[symbol] = []
            chunk_by_symbol[symbol].append(doc)
    
    print(f"[GraphRAG] ✓ Built symbol map with {len(chunk_by_symbol)} symbols")
    return GraphRAGRetriever(vectorstore, graph, documents, chunk_by_symbol)
