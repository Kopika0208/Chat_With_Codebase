# Graph-RAG Developer's Guide

## Extending the System

This guide explains how to customize and extend the Graph-RAG system for your specific needs.

## Adding Custom Edge Types

### Step 1: Define the Edge Type

Edge types are just strings, so adding a new type is simple. Choose a semantic name:

```python
# Good edge type names:
"depends_on"      # Dependency relationship
"used_by"         # Usage relationship
"imports_from"    # Import relationship
"returns_to"      # Return type relationship
"type_hints"      # Type annotation relationship
```

### Step 2: Create Edges in the Builder

In `ingestion/knowledge_graph.py`, add a method to `KnowledgeGraphBuilder`:

```python
def add_dependency_edges(self, dependency_map: Dict[str, List[str]]) -> None:
    """Add custom dependency edges.
    
    Args:
        dependency_map: Dict mapping node_id -> [dependent node_ids]
    """
    print("🔗 Adding dependency edges...")
    
    for source_id, targets in dependency_map.items():
        if source_id not in self.graph.nodes:
            continue
        
        for target_id in targets:
            if target_id not in self.graph.nodes:
                continue
            
            edge = KnowledgeGraphEdge(
                source_id=source_id,
                target_id=target_id,
                edge_type="depends_on",  # Custom type
                properties={
                    "dependency_type": "module_import",
                    "version": "1.0"
                }
            )
            self.graph.add_edge(edge)
    
    print(f"✅ Added {len(dependency_map)} dependency edges")
```

### Step 3: Call from Ingestion Pipeline

In `ingestion/ingest.py`, call your custom method:

```python
# After standard graph building
kg_builder.add_dependency_edges(your_dependency_map)
```

### Step 4: Use in Queries

Now traverse using your custom edge type:

```python
result = retriever.retrieve(
    query="What depends on this module?",
    edge_types=["depends_on"],  # Use custom type
    max_depth=2
)
```

## Adding Custom Traversal Filters

### Depth-Based Filtering

```python
class DepthAwareTraversal(GraphTraversal):
    """Traversal with custom depth-based weighting."""
    
    def traverse_with_depth_weights(self, anchor_nodes, max_depth, weight_fn):
        """Traverse with weighted depth impact.
        
        Args:
            weight_fn: Function(depth) -> float (multiplier)
        """
        result = self.traverse(anchor_nodes, max_depth)
        
        # Apply custom scoring based on depth
        weighted_nodes = {}
        for depth, nodes in result.reached_nodes_by_depth.items():
            weight = weight_fn(depth)
            for node_id in nodes:
                weighted_nodes[node_id] = weight
        
        return result, weighted_nodes
```

### Edge-Weight Based Filtering

```python
def traverse_high_importance(graph, anchor_nodes, max_depth):
    """Only traverse high-importance edges."""
    
    class HighImportanceTraversal(GraphTraversal):
        def _get_neighbors(self, node_id, edge_types, direction):
            neighbors = super()._get_neighbors(node_id, edge_types, direction)
            
            # Filter by importance property
            high_importance = [
                (n, et, p) for n, et, p in neighbors 
                if p.get("importance", 0) > 0.5
            ]
            return high_importance
    
    traversal = HighImportanceTraversal(graph.export_to_dict())
    return traversal.traverse(anchor_nodes, max_depth)
```

## Custom Scoring Functions

### Document Scoring by Graph Distance

```python
def score_by_graph_distance(docs, anchor_nodes, traversal_result):
    """Score documents by their distance in the graph.
    
    Closer to anchor = higher score.
    """
    scores = {}
    
    # Build distance map
    node_distances = {}
    for depth, nodes in traversal_result.reached_nodes_by_depth.items():
        for node in nodes:
            node_distances[node] = depth
    
    # Score each document
    for doc in docs:
        meta = doc.metadata or {}
        symbol = meta.get("symbol_name")
        path = meta.get("path")
        
        if symbol and path:
            node_id = f"{path}:{symbol}"
            distance = node_distances.get(node_id, 999)
            
            # Closer = higher score
            score = 1.0 / (1.0 + distance)
            scores[id(doc)] = score
    
    return scores
```

### Document Scoring by Edge Type

```python
def score_by_edge_type(docs, edge_type_importance):
    """Score documents based on edge types that led to them.
    
    Args:
        edge_type_importance: {"calls": 0.9, "dataflow": 0.7, ...}
    """
    scores = {}
    
    for doc in docs:
        meta = doc.metadata or {}
        edge_types_used = meta.get("edge_types_used", [])
        
        score = 0
        for edge_type in edge_types_used:
            score += edge_type_importance.get(edge_type, 0.5)
        
        scores[id(doc)] = score / max(len(edge_types_used), 1)
    
    return scores
```

## Supporting New Languages

### Add AST-Based Parser

In `ingestion/`, create `parser_rust.py`:

```python
def extract_rust_symbols(file_path: str, content: str) -> SymbolTable:
    """Extract symbols from Rust source code."""
    
    # Use tree-sitter for Rust parsing
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language
    except ImportError:
        return SymbolTable(file_path)
    
    language = get_language("rust")
    parser = Parser()
    parser.set_language(language)
    
    tree = parser.parse(content.encode())
    
    symbol_table = SymbolTable(file_path)
    
    # Walk AST and extract symbols
    # ... implementation ...
    
    return symbol_table
```

Then update `ingest.py`:

```python
from .parser_rust import extract_rust_symbols

# In ingestion loop
if ext == ".rs":
    symbol_table = extract_rust_symbols(rel_path, content)
    symbol_resolver.add_symbol_table(rel_path, symbol_table)
```

## Custom Knowledge Graph Loaders

### Load from Database

```python
class DatabaseGraphLoader:
    """Load knowledge graph from a database."""
    
    def __init__(self, connection_string):
        self.conn = create_connection(connection_string)
    
    def load_nodes(self):
        query = "SELECT id, type, name, file, line FROM kg_nodes"
        for row in self.conn.execute(query):
            yield KnowledgeGraphNode(
                node_id=row[0],
                node_type=row[1],
                name=row[2],
                file_path=row[3],
                line_number=row[4]
            )
    
    def load_edges(self):
        query = "SELECT source, target, type, properties FROM kg_edges"
        for row in self.conn.execute(query):
            yield KnowledgeGraphEdge(
                source_id=row[0],
                target_id=row[1],
                edge_type=row[2],
                properties=json.loads(row[3])
            )
    
    def to_knowledge_graph(self) -> KnowledgeGraph:
        kg = KnowledgeGraph()
        for node in self.load_nodes():
            kg.add_node(node)
        for edge in self.load_edges():
            kg.add_edge(edge)
        return kg
```

## Custom Retrieval Strategies

### Multi-Stage Retrieval

```python
class MultiStageGraphRAGRetriever(GraphRAGRetriever):
    """Retriever with multiple retrieval stages."""
    
    def retrieve_multi_stage(self, query: str, stages: List[Dict]) -> GraphRAGResult:
        """Execute multiple retrieval stages.
        
        Args:
            stages: [
                {
                    "name": "initial",
                    "k_initial": 5,
                    "max_depth": 1,
                    "edge_types": ["calls"]
                },
                {
                    "name": "expansion",
                    "k_initial": 3,
                    "max_depth": 2,
                    "edge_types": ["calls", "dataflow"]
                }
            ]
        """
        all_docs = []
        
        for stage in stages:
            print(f"🔍 Stage: {stage['name']}")
            result = self.retrieve(
                query=query,
                k_initial=stage.get("k_initial", 5),
                max_depth=stage.get("max_depth", 2),
                edge_types=stage.get("edge_types")
            )
            all_docs.extend(result.final_documents)
        
        # Deduplicate across all stages
        final_docs = self._deduplicate_documents(all_docs)
        
        return GraphRAGResult(
            query=query,
            anchor_documents=[],
            anchor_nodes=set(),
            expansion_result=None,
            expanded_documents=final_docs,
            final_documents=final_docs,
            statistics={"stages": len(stages)}
        )
```

### Query-Specific Strategies

```python
class AdaptiveGraphRAGRetriever(GraphRAGRetriever):
    """Automatically adapt retrieval strategy based on query."""
    
    def retrieve_adaptive(self, query: str) -> GraphRAGResult:
        """Adaptively choose retrieval parameters."""
        
        # Analyze query
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["who", "calls", "callers"]):
            # Impact analysis query
            strategy = {
                "edge_types": ["called_by"],
                "max_depth": 3,
                "direction": "in"
            }
        elif any(word in query_lower for word in ["how", "flow", "data"]):
            # Data flow query
            strategy = {
                "edge_types": ["dataflow", "calls", "defines", "uses"],
                "max_depth": 3,
                "direction": "both"
            }
        else:
            # Default: general query
            strategy = {
                "edge_types": None,
                "max_depth": 2,
                "direction": "both"
            }
        
        return self.retrieve(query, **strategy)
```

## Monitoring & Instrumentation

### Query Logging

```python
import logging
from datetime import datetime

class InstrumentedGraphRAGRetriever(GraphRAGRetriever):
    """Retriever with logging and instrumentation."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("GraphRAG")
    
    def retrieve(self, query: str, **kwargs) -> GraphRAGResult:
        start_time = datetime.now()
        
        try:
            result = super().retrieve(query, **kwargs)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Query successful in {elapsed:.2f}s: {query}")
            self.logger.info(f"  Nodes visited: {len(result.expansion_result.visited_nodes)}")
            self.logger.info(f"  Documents returned: {len(result.final_documents)}")
            
            return result
        
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Query failed in {elapsed:.2f}s: {query}")
            self.logger.error(f"  Error: {e}")
            raise
```

### Performance Profiling

```python
from typing import Callable
import time

def profile_retrieval(retriever: GraphRAGRetriever, queries: List[str]) -> Dict:
    """Profile retrieval performance across queries."""
    
    results = {
        "total_queries": len(queries),
        "queries": [],
        "avg_time": 0,
        "min_time": float('inf'),
        "max_time": 0
    }
    
    total_time = 0
    
    for query in queries:
        start = time.time()
        result = retriever.retrieve(query)
        elapsed = time.time() - start
        
        results["queries"].append({
            "query": query,
            "time": elapsed,
            "nodes_visited": len(result.expansion_result.visited_nodes),
            "docs_returned": len(result.final_documents)
        })
        
        total_time += elapsed
        results["min_time"] = min(results["min_time"], elapsed)
        results["max_time"] = max(results["max_time"], elapsed)
    
    results["avg_time"] = total_time / len(queries)
    
    return results
```

## Testing Custom Extensions

```python
import unittest

class TestCustomEdgeType(unittest.TestCase):
    """Test custom edge types."""
    
    def setUp(self):
        self.graph = KnowledgeGraph()
        self.builder = KnowledgeGraphBuilder()
    
    def test_custom_edge_creation(self):
        # Create nodes
        node1 = KnowledgeGraphNode(
            node_id="module1",
            node_type="module",
            name="module1",
            file_path="file1.py",
            line_number=1
        )
        node2 = KnowledgeGraphNode(
            node_id="module2",
            node_type="module",
            name="module2",
            file_path="file2.py",
            line_number=1
        )
        
        self.graph.add_node(node1)
        self.graph.add_node(node2)
        
        # Add custom edge
        edge = KnowledgeGraphEdge(
            source_id="module1",
            target_id="module2",
            edge_type="depends_on"
        )
        self.graph.add_edge(edge)
        
        # Verify
        outgoing = self.graph.get_outgoing_edges("module1")
        self.assertEqual(len(outgoing), 1)
        self.assertEqual(outgoing[0].edge_type, "depends_on")
    
    def test_custom_traversal(self):
        # Build test graph
        # ... setup code ...
        
        # Test custom traversal
        traversal = GraphTraversal(self.graph.export_to_dict())
        result = traversal.traverse(
            {"module1"},
            edge_types=["depends_on"]
        )
        
        self.assertIn("module2", result.visited_nodes)
```

## Documentation for Custom Features

### Template

When adding a custom feature, document it like this:

```python
def my_custom_function(param1: str, param2: int) -> Dict:
    """Brief description.
    
    Detailed explanation of what this does and how it works.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        Description of return value
    
    Examples:
        >>> result = my_custom_function("input", 42)
        >>> print(result)
        {'status': 'success'}
    
    Note:
        Any implementation notes or gotchas
    """
```

## Performance Optimization

### Caching Traversal Results

```python
from functools import lru_cache

class CachedGraphTraversal(GraphTraversal):
    """Traversal with caching for repeated queries."""
    
    @lru_cache(maxsize=128)
    def traverse_cached(self, anchor_nodes, max_depth, edge_types=None):
        """Cached version of traverse."""
        # Convert to frozenset for hashability
        return self.traverse(
            frozenset(anchor_nodes),
            max_depth,
            edge_types
        )
```

## Best Practices

1. **Type Hints**: Always use type hints for clarity
2. **Docstrings**: Document all public methods
3. **Testing**: Write unit tests for extensions
4. **Logging**: Use logging, not print() for production
5. **Error Handling**: Catch and handle exceptions gracefully
6. **Performance**: Profile before and after changes
7. **Backwards Compatibility**: Don't break existing APIs
8. **Documentation**: Update docs when adding features

---

For more information, see the main documentation files.
