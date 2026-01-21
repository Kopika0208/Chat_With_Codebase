# Graph-RAG Quick Start Guide

## Installation & Setup

### Prerequisites
```bash
Python 3.9+
CUDA 11.8+ (optional, for GPU acceleration)
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Setup
Create `.env` file:
```env
GROQ_API_KEY=your_api_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_api_key_here
```

## 5-Minute Quick Start

### Step 1: Ingest a Repository

```bash
cd Chat_With_Codebase
python -c "
from ingestion.ingest import ingest_repo
ingest_repo('repos/myrepo')  # Local path or GitHub URL
"
```

Output files created:
- `data/vector_store/` - FAISS embeddings
- `data/knowledge_graph.json` - Knowledge graph
- `data/call_graph.json` - Call relationships
- `data/symbol_table.json` - Symbol information

### Step 2: Launch Interactive App

```bash
cd retrieval/
streamlit run app.py
```

Then:
1. Navigate to `http://localhost:8501`
2. Select "Graph-RAG (Knowledge Graph + Vector Search)"
3. Ask a question like "Who calls the main function?"

### Step 3: Run Examples

```bash
python examples_graph_rag.py
```

This runs 5 examples demonstrating:
- Knowledge graph inspection
- Graph traversal
- Graph-RAG retrieval
- Comparison with semantic RAG

## Common Use Cases

### 1. Find All Functions That Call a Specific Function

**Question:** "Who calls the authentication function?"

**Graph-RAG Process:**
1. Vector search finds the `authenticate` function
2. Traverses `called_by` edges to find all callers
3. Returns complete list with code context

```python
result = retriever.retrieve(
    query="Who calls the authenticate function?",
    k_initial=1,
    max_depth=3,
    strategy="bfs"
)
```

### 2. Impact Analysis

**Question:** "What breaks if I remove this utility function?"

**Graph-RAG Process:**
1. Finds the utility function via vector search
2. Traverses `called_by` edges to find dependents
3. Shows all affected functions

```python
result = retriever.retrieve(
    query="What depends on the format_output utility?",
    max_depth=2,
    edge_types=["called_by"]
)
```

### 3. Feature Location

**Question:** "Where is the payment processing feature?"

**Graph-RAG Process:**
1. Searches for payment-related functions
2. Expands to related utilities via graph
3. Assembles complete feature context

```python
result = retriever.retrieve(
    query="Where is the payment processing implemented?",
    k_initial=5,
    max_depth=2,
    deduplicate=True
)
```

### 4. Data Flow Tracking

**Question:** "How does the user ID flow through the system?"

**Graph-RAG Process:**
1. Finds functions handling user ID
2. Follows dataflow edges through transformations
3. Shows complete data path

```python
result = retriever.retrieve(
    query="How does user ID flow through authentication?",
    edge_types=["dataflow", "calls"],
    max_depth=3
)
```

## Key Parameters

### retriever.retrieve()

| Parameter | Default | Description |
|-----------|---------|-------------|
| `query` | Required | User question |
| `k_initial` | 5 | Initial vector search results |
| `max_depth` | 2 | Graph traversal depth (1-4 recommended) |
| `strategy` | "bfs" | "bfs" (breadth-first) or "dfs" (depth-first) |
| `edge_types` | None | Filter by edge types (e.g., ["calls", "dataflow"]) |
| `direction` | "both" | "out" (outgoing), "in" (incoming), or "both" |
| `deduplicate` | True | Remove duplicate documents |

### Choosing Parameters

**For "Who calls X?" queries:**
```python
retrieve(
    query=...,
    k_initial=2,
    max_depth=2,
    strategy="bfs",
    edge_types=["called_by"],
    direction="in"  # Incoming edges only
)
```

**For "What breaks?" queries:**
```python
retrieve(
    query=...,
    k_initial=1,
    max_depth=3,
    strategy="bfs",
    edge_types=["calls", "called_by"],
    direction="both"
)
```

**For "How does it flow?" queries:**
```python
retrieve(
    query=...,
    k_initial=3,
    max_depth=3,
    strategy="bfs",
    edge_types=["calls", "dataflow", "defines", "uses"],
    direction="both"
)
```

## Understanding Results

### GraphRAGResult Object

```python
result = retriever.retrieve(query)

# Access components
print(f"Anchor documents: {len(result.anchor_documents)}")  # From vector search
print(f"Anchor nodes: {result.anchor_nodes}")                # Extracted node IDs
print(f"Visited nodes: {len(result.expansion_result.visited_nodes)}")  # After traversal
print(f"Final documents: {len(result.final_documents)}")    # For LLM context

# View statistics
print(result.summary())

# Access traversal details
for depth, nodes in result.expansion_result.reached_nodes_by_depth.items():
    print(f"Depth {depth}: {len(nodes)} nodes")
```

## Performance Tips

### 1. Start Small
```python
# Good for fast feedback
retrieve(query, k_initial=2, max_depth=1, strategy="bfs")

# Good for comprehensive context
retrieve(query, k_initial=5, max_depth=3, strategy="bfs")
```

### 2. Use Edge Type Filtering
```python
# Faster: only traverses specific relationships
retrieve(query, edge_types=["calls"])

# Slower: traverses all edges
retrieve(query)
```

### 3. Depth Limits
```python
max_depth=1  # Only direct neighbors (fast)
max_depth=2  # Recommended (balanced)
max_depth=3  # More context (slower)
max_depth=4+ # Very slow, diminishing returns
```

### 4. Strategy Selection
```python
strategy="bfs"   # Better for exploring breadth (default)
strategy="dfs"   # Better for deep paths
```

## Troubleshooting

### Issue: "No relevant code found"
**Solutions:**
- Increase `k_initial` to 10-20
- Try rephrasing the question
- Check that knowledge graph exists: `ls data/knowledge_graph.json`

### Issue: Slow retrieval
**Solutions:**
- Reduce `max_depth` to 1-2
- Use `edge_types` filter
- Switch to "dfs" strategy
- Check graph size: `python -c "import json; kg=json.load(open('data/knowledge_graph.json')); print(f'Nodes: {len(kg[\"nodes\"])}, Edges: {len(kg[\"edges\"])}')"

### Issue: Poor quality answers
**Solutions:**
- Verify anchor nodes are correct: `print(result.anchor_nodes)`
- Check if documents are deduplicated: Add `deduplicate=True`
- Try different edge types
- Increase `k_initial`

## Next Steps

1. **Read Full Documentation**: [GRAPH_RAG_DOCUMENTATION.md](GRAPH_RAG_DOCUMENTATION.md)
2. **Explore Examples**: `python examples_graph_rag.py`
3. **Run Interactive App**: `streamlit run retrieval/app.py`
4. **Customize**: Modify edge types, traversal strategy for your use case

## Architecture Overview

```
Your Question
    ↓
[Vector Search] ← FAISS index
    ↓
Anchor Docs + Extracted Nodes
    ↓
[Graph Traversal] ← Knowledge Graph
    ↓
Expanded Nodes
    ↓
[Document Collection]
    ↓
Final Context
    ↓
[LLM] → Answer
```

## API Quick Reference

### Core Classes

**GraphRAGRetriever**
```python
from retrieval.graph_rag import GraphRAGRetriever

retriever.retrieve(query, k_initial=5, max_depth=2, strategy="bfs")
retriever.retrieve_with_debug(query, k_initial=5, max_depth=2)
```

**GraphTraversal**
```python
from retrieval.graph_traversal import load_knowledge_graph

graph = load_knowledge_graph("data/knowledge_graph.json")
result = graph.traverse(anchor_nodes, max_depth=2, strategy="bfs")
paths = graph.find_paths(source, target, max_length=5)
context = graph.get_node_context(node_id, radius=1)
```

**Ingestion**
```python
from ingestion.ingest import ingest_repo

ingest_repo("https://github.com/user/repo.git")
ingest_repo("/local/path/to/repo")
```

## Support

- **Documentation**: [GRAPH_RAG_DOCUMENTATION.md](GRAPH_RAG_DOCUMENTATION.md)
- **Examples**: Run `python examples_graph_rag.py`
- **Source Code**: See `retrieval/` and `ingestion/` directories

Happy Graph-RAG querying! 🚀
