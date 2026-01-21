# Graph-RAG System Documentation

## Overview

This is a **production-grade Graph-RAG (Retrieval-Augmented Generation) system** for intelligent codebase understanding. It combines:

- **Vector Search**: Semantic similarity for initial retrieval
- **Knowledge Graph**: Structured code relationships (calls, dataflow, inheritance, etc.)
- **Graph Traversal**: BFS/DFS expansion from anchor nodes
- **Context Assembly**: Intelligent collection of related code

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                   INGESTION PIPELINE                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Code Parsing → Symbol Extraction → Call Graph          │
│       ↓              ↓                   ↓               │
│   AST/Tree-sitter  Scopes & Types   Function Calls      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │     KNOWLEDGE GRAPH BUILDER                      │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Nodes:                                           │   │
│  │  - Functions, classes, methods, variables       │   │
│  │  - Stable IDs: file.py:symbol_name              │   │
│  │                                                  │   │
│  │ Edges (Typed Relationships):                    │   │
│  │  - calls / called_by                            │   │
│  │  - defines / uses                               │   │
│  │  - dataflow                                      │   │
│  │  - inherits / overrides                         │   │
│  │  - contains (parent-child)                      │   │
│  │  - test_relationship                            │   │
│  └──────────────────────────────────────────────────┘   │
│                      ↓                                   │
│        Persist: knowledge_graph.json                     │
│        Also: FAISS vector store (embeddings)            │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  RETRIEVAL PIPELINE                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. VECTOR SEARCH                                       │
│     Query → Embeddings → FAISS → Anchor Docs            │
│                                                          │
│  2. ANCHOR NODE EXTRACTION                              │
│     Extract node IDs from doc metadata                  │
│                                                          │
│  3. GRAPH TRAVERSAL (BFS/DFS)                           │
│     Anchor → Neighbors (max_depth=2)                    │
│     Filter by edge types: calls, dataflow, etc.         │
│                                                          │
│  4. DOCUMENT COLLECTION                                 │
│     Expanded nodes → Code chunks from index             │
│                                                          │
│  5. CONTEXT ASSEMBLY                                    │
│     Deduplicate → Deduplicate → LLM Prompt              │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              LLM ANSWER GENERATION                       │
├─────────────────────────────────────────────────────────┤
│  Prompt = Context + Sources + Question                  │
│  LLM outputs: Answer with file/line references          │
└─────────────────────────────────────────────────────────┘
```

## File Structure

```
Chat_With_Codebase/
├── ingestion/
│   ├── ingest.py                 # Main ingestion orchestrator
│   ├── symbols.py                # Symbol table & extraction
│   ├── callgraph.py              # Call graph extraction
│   ├── dataflow.py               # Data flow analysis
│   ├── knowledge_graph.py         # Knowledge graph builder
│   └── ...
│
├── retrieval/
│   ├── __init__.py               # Package init
│   ├── app.py                    # Streamlit UI
│   ├── cache.py                  # Resource caching
│   ├── graph_traversal.py        # Graph BFS/DFS engine
│   ├── graph_rag.py              # Graph-RAG retriever
│   ├── retrieval.py              # Semantic retrieval
│   ├── unified_retrieval.py      # Unified retrieval
│   └── ...
│
├── data/
│   ├── vector_store/             # FAISS index
│   ├── knowledge_graph.json       # Persisted KG
│   ├── call_graph.json           # Call relationships
│   └── symbol_table.json         # Symbol information
│
└── examples_graph_rag.py         # Example usage
```

## Knowledge Graph Format

### Nodes
```json
{
  "id": "src/auth.py:authenticate",
  "type": "function",
  "name": "authenticate",
  "file": "src/auth.py",
  "line": 42,
  "properties": {
    "is_private": false,
    "is_static": false,
    "docstring": "Authenticates user credentials...",
    "parent_symbol": null
  }
}
```

### Edges
```json
{
  "source": "src/auth.py:authenticate",
  "target": "src/utils.py:hash_password",
  "type": "calls",
  "properties": {
    "call_count": 1
  }
}
```

### Edge Types
- **calls** / **called_by**: Function call relationships
- **defines** / **uses**: Variable/symbol definitions and uses
- **dataflow**: Data flow dependencies (def-use chains)
- **inherits** / **overrides**: Class hierarchy
- **sibling_method**: Methods in same class
- **contains**: Parent-child relationships
- **test_relationship**: Test code references production

## Usage

### 1. Ingest a Repository

```python
from ingestion.ingest import ingest_repo

# Ingest from GitHub or local path
ingest_repo("https://github.com/user/repo.git")
# or
ingest_repo("/path/to/local/repo")
```

This creates:
- `data/vector_store/` - FAISS embeddings index
- `data/knowledge_graph.json` - Knowledge graph with nodes and edges
- `data/call_graph.json` - Call relationships
- `data/symbol_table.json` - Symbol information

### 2. Query with Graph-RAG

```python
from retrieval.graph_rag import create_graph_rag_retriever
from retrieval.cache import get_vectorstore

vectorstore = get_vectorstore()
retriever = create_graph_rag_retriever(
    vectorstore,
    "data/knowledge_graph.json",
    documents
)

# Query with graph expansion
result = retriever.retrieve(
    query="Who calls the authentication function?",
    k_initial=5,           # Initial vector search results
    max_depth=2,           # Graph traversal depth
    strategy="bfs",        # BFS or DFS
    edge_types=["calls", "called_by"],
    deduplicate=True
)

print(f"Anchor nodes: {result.anchor_nodes}")
print(f"Total visited: {len(result.expansion_result.visited_nodes)}")
print(f"Final docs: {len(result.final_documents)}")
```

### 3. Graph Traversal

```python
from retrieval.graph_traversal import load_knowledge_graph

graph = load_knowledge_graph("data/knowledge_graph.json")

# Find all functions called by a specific function
result = graph.traverse(
    anchor_nodes={"src/main.py:process_data"},
    max_depth=2,
    strategy="bfs",
    edge_types=["calls"],
    direction="out"  # Outgoing edges
)

for node_id in result.visited_nodes:
    print(node_id)
```

### 4. Use in Streamlit App

```bash
cd retrieval/
streamlit run app.py
```

Then:
1. Select **"Graph-RAG (Knowledge Graph + Vector Search)"** from the dropdown
2. Set traversal depth and strategy
3. Ask questions like:
   - "Who calls this function?"
   - "What breaks if I remove this?"
   - "How does data flow through the system?"

## Key Differences from Semantic-Only RAG

### Semantic RAG
```
Query → Embeddings → FAISS similarity search → Top K docs → LLM
```
- Fast, simple
- Works for "What does this do?"
- Misses structural relationships
- May return irrelevant similar code

### Graph-RAG
```
Query → Embeddings → FAISS → Anchor nodes → Graph traversal → Expanded docs → LLM
```
- Finds structurally related code
- Answers "If I change X, what breaks?"
- Assembles complete context
- Demonstrates code impact analysis

## Query Examples

### Question Type 1: Function Dependencies
**Q:** "Who calls the `validate_input` function?"
- **Semantic RAG**: Returns similar code about validation
- **Graph-RAG**: Finds `validate_input`, traverses `called_by` edges, returns actual callers

### Question Type 2: Impact Analysis
**Q:** "What breaks if I remove the `cache_result` utility?"
- **Semantic RAG**: Returns code mentioning "cache" (may be unrelated)
- **Graph-RAG**: Finds `cache_result`, traverses `called_by` edges, shows all dependents

### Question Type 3: Data Flow
**Q:** "How does the user ID flow through the authentication system?"
- **Semantic RAG**: Returns snippets with "user ID" (noisy)
- **Graph-RAG**: Follows dataflow edges from user ID to all uses

### Question Type 4: Feature Location
**Q:** "Where is the payment processing feature implemented?"
- **Semantic RAG**: Returns similar code
- **Graph-RAG**: Finds payment functions, expands to related utilities, shows complete feature

## Performance Characteristics

### Ingestion
- **Time**: O(n) where n = source files
- **Memory**: O(nodes + edges) = O(symbols + relationships)
- **Disk**: ~1-10 MB for knowledge graph JSON

### Retrieval (per query)
- **Vector search**: O(k log m) where m = indexed chunks, k = results
- **Graph traversal**: O(V + E) where V = visited nodes, E = edges
- **Total**: Milliseconds to seconds depending on graph size and depth

### Scalability
- Works well for codebases with 100-100,000 functions
- Graph traversal depth ≤ 3 recommended for performance
- FAISS provides sub-millisecond vector search

## Advanced Features

### 1. Edge Type Filtering
```python
# Only traverse function calls, not dataflow
result = graph.traverse(
    anchor_nodes={"src/main.py:process"},
    edge_types=["calls", "called_by"]
)
```

### 2. Directional Traversal
```python
# Find only callers (incoming edges)
result = graph.traverse(
    anchor_nodes={"src/auth.py:authenticate"},
    edge_types=["called_by"],
    direction="in"
)
```

### 3. Path Finding
```python
# Find shortest paths between two functions
paths = graph.find_paths(
    source="src/main.py:process",
    target="src/db.py:query",
    max_length=5
)
```

### 4. Node Context
```python
# Get node and immediate neighbors
context = graph.get_node_context(
    node_id="src/utils.py:format_output",
    radius=1,
    edge_types=["calls", "called_by"]
)
```

## Extending the System

### Adding New Edge Types
Edit `ingestion/knowledge_graph.py`:
```python
# In KnowledgeGraphBuilder.add_custom_edges():
edge = KnowledgeGraphEdge(
    source_id=source,
    target_id=target,
    edge_type="custom_relationship",  # New type
    properties={"metadata": "..."}
)
self.graph.add_edge(edge)
```

### Custom Traversal Filters
```python
result = graph.traverse(
    anchor_nodes=set(...),
    max_depth=3,
    strategy="bfs",
    edge_types=["calls", "dataflow"],  # Only these types
    direction="both"  # out, in, or both
)
```

### Custom Scoring
Implement in retrieval pipeline:
```python
def custom_score_documents(docs, query, traversal_result):
    """Score documents based on graph distance."""
    for doc in docs:
        # Get graph distance
        # Apply custom scoring
    return sorted_docs
```

## Troubleshooting

### No documents retrieved
- Increase `k_initial` (initial vector search)
- Increase `max_depth` for graph traversal
- Check that knowledge graph was built (knowledge_graph.json exists)

### Graph traversal too slow
- Reduce `max_depth`
- Filter by specific `edge_types`
- Check knowledge graph size

### Poor quality answers
- Verify anchor nodes extracted correctly
- Check edge types are appropriate for query
- Try different retrieval strategies

## References

- **GraphRAG Paper**: [Hierarchical Indexing of Code Repositories (Gao et al., 2024)](https://arxiv.org/abs/2406.06337)
- **Knowledge Graphs**: Structured knowledge representation
- **FAISS**: Facebook AI Similarity Search
- **Langchain**: LLM integration framework

## Testing

Run the example script:
```bash
python examples_graph_rag.py
```

This demonstrates:
1. Ingestion
2. Graph inspection
3. Traversal
4. Retrieval
5. Comparison with semantic RAG

## License

This system is part of the PRAGATI project.

## Author

Built for intelligent codebase understanding with Graph-RAG.
