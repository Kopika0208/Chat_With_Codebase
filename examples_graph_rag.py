#!/usr/bin/env python3
"""
Graph-RAG Example Usage Script

Demonstrates the complete Graph-RAG pipeline:
1. Ingestion: Building knowledge graph
2. Retrieval: Graph-aware context assembly
3. Query: Answering structural questions
"""

import os
import sys
import json

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from ingestion.ingest import ingest_repo
from retrieval.graph_rag import create_graph_rag_retriever
from retrieval.graph_traversal import load_knowledge_graph
from cache import get_vectorstore
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings


def example_ingestion():
    """Example: Ingest a repository and build knowledge graph."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Repository Ingestion")
    print("="*70)
    
    repo_path = "repos/myrepo"  # Local path or GitHub URL
    
    print(f"\n📥 Ingesting repository from: {repo_path}")
    print("   This will:")
    print("   1. Parse Python/JS/TS code")
    print("   2. Extract symbols (functions, classes, methods)")
    print("   3. Build call graph")
    print("   4. Build knowledge graph with typed relationships")
    print("   5. Create FAISS vector index")
    
    try:
        ingest_repo(repo_path)
        print("\n✅ Ingestion complete!")
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")
        return False
    
    return True


def example_graph_inspection():
    """Example: Inspect the knowledge graph structure."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Knowledge Graph Inspection")
    print("="*70)
    
    kg_path = os.path.join(PROJECT_ROOT, "data/knowledge_graph.json")
    
    if not os.path.exists(kg_path):
        print(f"❌ Knowledge graph not found at {kg_path}")
        return False
    
    print(f"\n📖 Loading knowledge graph from: {kg_path}")
    
    try:
        with open(kg_path, "r") as f:
            kg_data = json.load(f)
        
        metadata = kg_data.get("metadata", {})
        print(f"\n📊 Knowledge Graph Statistics:")
        print(f"   Nodes: {metadata.get('node_count', len(kg_data.get('nodes', [])))}")
        print(f"   Edges: {metadata.get('edge_count', len(kg_data.get('edges', [])))}")
        
        # Count edge types
        edge_types = {}
        for edge in kg_data.get("edges", []):
            edge_type = edge.get("type", "unknown")
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        print(f"\n   Edge types:")
        for edge_type, count in sorted(edge_types.items()):
            print(f"      {edge_type}: {count}")
        
        # Show sample nodes
        nodes = kg_data.get("nodes", [])
        if nodes:
            print(f"\n   Sample nodes:")
            for node in nodes[:5]:
                node_id = node.get("id", "unknown")
                node_type = node.get("type", "unknown")
                name = node.get("name", "unknown")
                print(f"      [{node_type}] {name} ({node_id})")
        
        return True
    
    except Exception as e:
        print(f"❌ Error loading knowledge graph: {e}")
        return False


def example_graph_traversal():
    """Example: Perform graph traversal from anchor nodes."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Graph Traversal")
    print("="*70)
    
    kg_path = os.path.join(PROJECT_ROOT, "data/knowledge_graph.json")
    
    if not os.path.exists(kg_path):
        print(f"❌ Knowledge graph not found at {kg_path}")
        return False
    
    print(f"\n🚀 Loading graph traversal engine...")
    
    try:
        graph = load_knowledge_graph(kg_path)
        
        # Get some nodes to traverse from
        sample_nodes = list(graph.nodes.keys())[:3]
        
        if not sample_nodes:
            print("❌ No nodes in knowledge graph")
            return False
        
        print(f"\n   Sample anchor nodes: {sample_nodes}")
        
        # Perform BFS traversal
        print(f"\n📍 Performing BFS traversal (max_depth=2)...")
        result = graph.traverse(
            anchor_nodes=set(sample_nodes),
            max_depth=2,
            strategy="bfs",
            edge_types=["calls", "called_by", "contains"],
            direction="both"
        )
        
        print(f"\n   Visited {len(result.visited_nodes)} nodes:")
        for depth in sorted(result.reached_nodes_by_depth.keys()):
            nodes_at_depth = result.reached_nodes_by_depth[depth]
            print(f"      Depth {depth}: {len(nodes_at_depth)} nodes")
        
        print(f"   Traversed {len(result.edges_traversed)} edges")
        
        # Show some edges
        if result.edges_traversed:
            print(f"\n   Sample edges:")
            for source, target, edge_type in result.edges_traversed[:3]:
                print(f"      {edge_type}: {source} -> {target}")
        
        return True
    
    except Exception as e:
        print(f"❌ Error during graph traversal: {e}")
        return False


def example_graph_rag_retrieval():
    """Example: Perform Graph-RAG retrieval."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Graph-RAG Retrieval")
    print("="*70)
    
    kg_path = os.path.join(PROJECT_ROOT, "data/knowledge_graph.json")
    vector_dir = os.path.join(PROJECT_ROOT, "data/vector_store")
    
    if not os.path.exists(kg_path):
        print(f"❌ Knowledge graph not found")
        return False
    
    if not os.path.exists(vector_dir):
        print(f"❌ Vector store not found")
        return False
    
    print(f"\n🔍 Initializing Graph-RAG retriever...")
    
    try:
        # Load vectorstore
        embeddings = HuggingFaceEmbeddings(
            model_name="mixedbread-ai/mxbai-embed-large-v1"
        )
        vectorstore = FAISS.load_local(
            vector_dir, embeddings, allow_dangerous_deserialization=True
        )
        
        # Get all documents
        all_documents = list(vectorstore.docstore._dict.values())
        
        # Create retriever
        retriever = create_graph_rag_retriever(vectorstore, kg_path, all_documents)
        
        # Example queries that benefit from Graph-RAG
        example_queries = [
            "Who calls the main function?",
            "What functions depend on this utility?",
            "How does the data flow through the system?",
            "Where is this feature implemented?",
        ]
        
        print(f"\n💬 Example queries for Graph-RAG:")
        for query in example_queries:
            print(f"   - {query}")
        
        # Run a sample query
        if len(example_queries) > 0:
            sample_query = example_queries[0]
            print(f"\n🚀 Running sample query: {sample_query!r}")
            
            result = retriever.retrieve(
                query=sample_query,
                k_initial=3,
                max_depth=2,
                strategy="bfs",
                deduplicate=True
            )
            
            print(f"\n📊 Retrieval Results:")
            print(f"   Anchor documents (from vector search): {len(result.anchor_documents)}")
            print(f"   Anchor nodes: {len(result.anchor_nodes)}")
            print(f"   Total nodes visited: {len(result.expansion_result.visited_nodes)}")
            print(f"   Max depth reached: {max(result.expansion_result.reached_nodes_by_depth.keys()) if result.expansion_result.reached_nodes_by_depth else 0}")
            print(f"   Final documents (after expansion): {len(result.final_documents)}")
            
            if result.final_documents:
                print(f"\n   Top document:")
                doc = result.final_documents[0]
                meta = doc.metadata or {}
                print(f"      Path: {meta.get('path', 'unknown')}")
                print(f"      Symbol: {meta.get('symbol_name', 'unknown')}")
                print(f"      Lines: {meta.get('start_line', '?')}-{meta.get('end_line', '?')}")
        
        return True
    
    except Exception as e:
        print(f"❌ Error during Graph-RAG retrieval: {e}")
        import traceback
        traceback.print_exc()
        return False


def example_comparison():
    """Example: Compare semantic vs Graph-RAG retrieval."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Semantic vs Graph-RAG Comparison")
    print("="*70)
    
    print("""
Graph-RAG advantages over semantic-only RAG:

1. **Structural Awareness**
   - Semantic: "Find similar code"
   - Graph-RAG: "Find code PLUS related functions via call graph"

2. **Dependency Tracking**
   - Semantic: Returns snippets by embedding similarity
   - Graph-RAG: Expands to all functions called by initial matches

3. **Question Answering**
   - Semantic: Good for "What does this do?"
   - Graph-RAG: Good for "If I change this, what breaks?"

4. **Context Assembly**
   - Semantic: Single-pass retrieval
   - Graph-RAG: Multi-hop context collection via knowledge graph

Example Scenarios:

Query: "Who calls the authentication function?"
   Semantic: Returns similar code chunks
   Graph-RAG: Finds auth function, traverses incoming edges to find callers

Query: "What breaks if I remove this utility?"
   Semantic: Returns similar code (may miss the actual impact)
   Graph-RAG: Finds utility, traverses "called_by" edges to find all dependents

Query: "How does this data flow through the system?"
   Semantic: Searches by data-related keywords
   Graph-RAG: Follows dataflow edges in knowledge graph
    """)


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("GRAPH-RAG SYSTEM - COMPREHENSIVE EXAMPLE")
    print("="*70)
    
    print("""
This script demonstrates the Graph-RAG pipeline:

1. INGESTION: Build knowledge graph from codebase
2. INSPECTION: Examine graph structure and statistics
3. TRAVERSAL: Perform BFS/DFS on knowledge graph
4. RETRIEVAL: Execute Graph-RAG queries
5. COMPARISON: Understand advantages over semantic RAG
    """)
    
    # Run examples
    examples = [
        # ("Ingestion", example_ingestion),  # Comment out if repo already ingested
        ("Graph Inspection", example_graph_inspection),
        ("Graph Traversal", example_graph_traversal),
        ("Graph-RAG Retrieval", example_graph_rag_retrieval),
        ("Comparison", example_comparison),
    ]
    
    results = {}
    for name, func in examples:
        try:
            success = func()
            results[name] = "✅ PASSED" if success else "❌ FAILED"
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = "❌ ERROR"
    
    # Summary
    print("\n" + "="*70)
    print("EXECUTION SUMMARY")
    print("="*70)
    for name, result in results.items():
        print(f"   {name}: {result}")
    
    print("\n" + "="*70)
    print("✅ Examples complete!")
    print("="*70)


if __name__ == "__main__":
    main()
