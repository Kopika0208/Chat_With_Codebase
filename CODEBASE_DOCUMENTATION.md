# Chat With Codebase - Complete File Documentation

This document provides a comprehensive overview of every file in the Chat With Codebase project, explaining their purpose, functionality, and relationships.

---

## 📁 Project Structure Overview

```
Chat_With_Codebase/
├── retrieval/              # Query processing, retrieval, and LLM orchestration
├── ingestion/              # Code parsing, vectorization, and graph building
├── code_health/            # Code quality analysis and scoring
├── data/                   # Ingested repository data and embeddings
├── repos/                  # Ingested repository source code
├── lib/                    # Third-party JavaScript libraries
├── retrieval/app.py        # Main Streamlit web application
└── requirements.txt        # Python dependencies
```

---

## 🚀 MAIN APPLICATION

### `retrieval/app.py` (Main Streamlit UI)
**Purpose:** The central web application interface that users interact with.

**Key Features:**
- Multi-repository management and selection
- Repository ingestion/indexing interface
- Call graph visualization
- Onboarding & documentation tabs (Overview, Entry/Exit Points, Roadmap, File Structure, Navigation, Code Health)
- Query interface with Graph-RAG retrieval (hardcoded to use Graph-RAG, max_depth=4, dfs strategy)
- Answer display with code matches, sources, and statistics
- LangSmith integration for tracing

**Key Functions:**
- `run_query_pipeline()` - Execute complete query pipeline with multi-hop retrieval
- `run_graph_rag_pipeline()` - Execute Graph-RAG query pipeline with knowledge graph traversal

**UI Components:**
- Repository selector and ingestion form
- Call graph explorer
- Onboarding tabs with project statistics
- Query input and run button
- Results display with code snippets and metadata

---

## 📥 INGESTION MODULE (`ingestion/`)

### `ingestion/ingest.py` (Main Ingestion Orchestrator)
**Purpose:** Orchestrates the complete ingestion pipeline for code repositories.

**Key Functions:**
- `ingest_repo()` - Main entry point for ingesting a repository
  - Clones or opens repository
  - Parses code using multiple strategies
  - Builds call graphs, symbol tables, knowledge graphs
  - Creates FAISS vector embeddings
  - Saves all outputs to `data/` directory

**Constants:**
- `EXTENSIONS` - Supported file types: .py, .js, .java, .ts, .md, .txt, .go, .cpp, .c, .h, .rs
- `EMBED_MODEL` - Uses "mixedbread-ai/mxbai-embed-large-v1" for embeddings
- `VECTOR_DIR`, `CALLGRAPH_PATH` - Default paths for storing vectorized data

**Multi-repo Support:** Paths are dynamically generated per repository

---

### `ingestion/callgraph.py` (Call Graph Extraction)
**Purpose:** Extracts function-to-function call relationships from source code.

**Supported Languages:**
- Python (via AST)
- JavaScript/TypeScript (via regex or tree-sitter)

**Key Functions:**
- `extract_python_calls()` - Uses Python AST to find function calls within files
- `extract_js_calls()` - Regex-based extraction for JS/TS files
- Returns list of (caller_name, callee_symbol) tuples

**Output Format:**
```json
{
  "function_a": ["function_b", "function_c"],
  "function_b": ["function_d"]
}
```

---

### `ingestion/symbols.py` (Symbol Table & Symbol Extraction)
**Purpose:** Builds comprehensive symbol tables and extracts all symbols from code.

**Core Classes:**
- `TypeInfo` - Represents type information for symbols (name, module, base_types)
- `Symbol` - Represents any symbol in code (function, class, variable, etc.)
  - Properties: name, kind, scope_id, line numbers, file path, type hints, parent/child relationships, references
- `SymbolTable` - Dictionary-like storage of all symbols in repository

**Key Functions:**
- `extract_python_symbols()` - AST-based extraction for Python
- `extract_js_symbols()` - Regex-based extraction for JavaScript
- Symbol relationship mapping (parent-child, references)

**Symbol Types:**
- function_definition, method_definition
- class_definition
- variable_assignment
- import_statement
- attribute_definition

---

### `ingestion/chunking.py` (Code Chunking & Parsing)
**Purpose:** Splits code into meaningful chunks using multiple parsing strategies.

**Parsing Strategies (in order of preference):**
1. **Tree-sitter** - Robust language-agnostic parser for precise code structure
2. **AST (Python)** - Abstract Syntax Tree for Python
3. **Regex** - Fallback heuristic splitter for unsupported languages

**Key Functions:**
- `simple_function_split()` - Regex-based fallback chunking
- `get_ast_chunks()` - Python AST-based chunking
- `get_tree_sitter_chunks()` - Tree-sitter chunking with proper nesting

**Chunk Metadata:**
- start_line, end_line
- node_type (function, class, import, etc.)
- name (symbol name)
- language
- parser_used (which parser extracted it)
- content (actual code)

---

### `ingestion/knowledge_graph.py` (Knowledge Graph Builder)
**Purpose:** Builds a semantic knowledge graph representing relationships between code symbols.

**Core Classes:**
- `KnowledgeGraphNode` - Represents a node (function, class, variable, etc.)
  - Unique node_id format: `file.py:symbol_name`
  - Properties store semantic information
- `KnowledgeGraphEdge` - Represents relationships between nodes
  - Types: calls, called_by, contains, dataflow, imports, type_ref, etc.
- `KnowledgeGraph` - Stores all nodes and edges

**Key Functions:**
- `build_knowledge_graph()` - Constructs full knowledge graph from symbols and call graphs
- `get_semantic_neighbors()` - Finds related symbols in graph
- `compute_node_importance()` - Weights nodes by centrality/usage

**Edge Types:**
- **calls / called_by** - Function call relationships
- **contains** - File contains symbol, class contains method
- **dataflow** - Variable/parameter dependencies
- **imports** - Import relationships
- **type_ref** - Type references (for type hinting)
- **semantic** - Semantic similarity relationships

---

### `ingestion/dataflow.py` (Data Flow Analysis)
**Purpose:** Analyzes how data flows through the code.

**Key Analysis:**
- Variable assignment tracking
- Parameter passing analysis
- Return value propagation
- Inter-procedural data flow

**Output:**
```json
{
  "function_name": {
    "parameters": [{"name": "param", "type": "..."}],
    "returns": "type",
    "uses": ["var1", "var2"],
    "modifies": ["global_var"]
  }
}
```

---

### `ingestion/resolver.py` (Symbol Resolution)
**Purpose:** Resolves symbol references to their definitions for better linking.

**Key Functions:**
- `resolve_symbol_reference()` - Finds what a symbol reference points to
- `build_reference_map()` - Maps all references to their definitions
- Handles scoping and module resolution

---

### `ingestion/utils.py` (Ingestion Utilities)
**Purpose:** Common utility functions for the ingestion module.

**Key Functions:**
- `load_json()` - Safe JSON loading
- `save_json()` - Save data with formatting
- `get_file_language()` - Detect language from file extension
- `is_code_file()` - Check if file should be processed

---

## 🔍 RETRIEVAL MODULE (`retrieval/`)

### `retrieval/app.py` (See above in MAIN APPLICATION)

### `retrieval/cache.py` (Caching Layer)
**Purpose:** Centralized caching for expensive operations with multi-repo support.

**Cached Resources:**
- **Vectorstore** - FAISS index for vector similarity search
- **Call Graph** - Cached call graph JSON
- **Knowledge Graph** - Cached knowledge graph
- **Symbol Table** - Cached symbol table
- **Dataflow Data** - Cached dataflow analysis
- **LLM** - Shared LLM instance (Groq)
- **Embeddings** - Shared embedding model

**Key Functions:**
- `get_vectorstore(repo_name)` - Load FAISS vectorstore
- `get_llm()` - Get LLM instance (ChatGroq)
- `get_embeddings()` - Get embedding model
- `get_graph_rag_retriever()` - Create Graph-RAG retriever
- `load_*_cached()` - Various cached loaders

**Caching Strategy:**
- Uses `@st.cache_resource` for Streamlit session persistence
- Repo-specific caching with `repo_name` parameter
- Cache invalidation on repo switch

---

### `retrieval/retrieval.py` (Core Retrieval Functions)
**Purpose:** Core retrieval logic combining vector search, reranking, and multi-hop retrieval.

**Key Functions:**
- `infer_metadata_filters_from_query()` - Extract implicit filters (language, node_type, file patterns)
- `stage1_vector_search()` - Initial vector similarity search
- `hybrid_rerank()` - Combine BM25 and semantic reranking
- `multi_hop_retrieve()` - Follow related files/symbols for multi-hop retrieval
- `deduplicate_docs()` - Remove semantic duplicates
- `get_expanded_context()` - Fetch surrounding code for context
- `symbol_aware_retrieve()` - Symbol-driven ranking for better results
- `build_context_and_sources()` - Format context for LLM

**Retrieval Pipeline:**
1. Query rewriting (optional)
2. Metadata filter inference
3. Vector search or multi-hop retrieval
4. Deduplication
5. Result limiting
6. Context expansion
7. LLM formatting

---

### `retrieval/graph_rag.py` (Graph-RAG Implementation)
**Purpose:** Implements the Graph-RAG retrieval strategy using knowledge graph traversal.

**Core Classes:**
- `GraphRAGResult` - Result object containing:
  - query
  - anchor_documents (initial vector search results)
  - anchor_nodes (initial symbols found)
  - expansion_result (traversal results)
  - final_documents (deduplicated results)

**Key Functions:**
- `create_graph_rag_retriever()` - Create a Graph-RAG retriever instance
- `retrieve()` - Main retrieval method:
  1. Vector search for anchor nodes
  2. Knowledge graph traversal from anchors
  3. Deduplicate results
  4. Return final documents

**Graph-RAG Strategy:**
- **Vector Search** → Find initial relevant code chunks
- **Graph Traversal** → Expand by following relationships (calls, imports, dataflow)
- **Deduplication** → Remove semantic duplicates
- **Ranking** → Return most relevant results

---

### `retrieval/graph_traversal.py` (Knowledge Graph Traversal)
**Purpose:** Implements graph traversal algorithms for exploring knowledge graph.

**Core Classes:**
- `TraversalStrategy` - Enum for traversal methods (BFS, DFS)
- `TraversalResult` - Results of graph traversal

**Key Functions:**
- `traverse_graph()` - Main traversal function
  - Parameters: start_nodes, max_depth, strategy, edge_types, visited limit
  - Returns: visited_nodes, edges_traversed, expansion_results
- `load_knowledge_graph()` - Load KG from JSON

**Traversal Modes:**
- **BFS** (Breadth-First) - Explore all neighbors at depth N before N+1
- **DFS** (Depth-First) - Explore deeply first, then backtrack

**Default Settings (in app.py):**
- max_depth = 4
- strategy = "dfs"
- edge_types = ["calls", "called_by", "contains", "dataflow"]
- deduplicate = True

---

### `retrieval/query_understanding.py` (Advanced Query Understanding)
**Purpose:** Advanced query analysis to understand user intent and identify relevant symbols.

**Core Classes:**
- `QueryIntentType` - Enum of intent types:
  - FIND_FUNCTION, FIND_CLASS, FIND_PATTERN, FIND_USAGE
  - FIND_IMPLEMENTATION, FIND_CALLER, FIND_RELATED
  - UNDERSTAND_FLOW, FIND_SIMILAR, CUSTOM
- `QueryAnalyzer` - Analyzes query structure and extracts intent

**Key Functions:**
- `analyze_query()` - Extract intent, keywords, and referenced symbols
- `identify_symbols()` - Find symbols mentioned or inferred from query
- `enhance_with_kg()` - Expand query understanding using knowledge graph

**Intent Detection:**
- Pattern matching for common query types
- Symbol extraction and type inference
- Confidence scoring

---

### `retrieval/reasoning.py` (Multi-step Reasoning)
**Purpose:** Implements multi-step reasoning chains for complex queries.

**Key Features:**
- Query decomposition into sub-queries
- Graph-walk based reasoning
- Symbol relationship exploration
- Answer synthesis from multiple sources

---

### `retrieval/symbol_driven_ranking.py` (Symbol-Aware Ranking)
**Purpose:** Ranks retrieval results based on symbol properties and relationships.

**Key Functions:**
- `symbol_aware_retrieve()` - Retrieval with symbol-based ranking
- `compute_symbol_importance()` - Weight symbols by centrality
- `apply_symbol_context()` - Boost results mentioning relevant symbols

---

### `retrieval/unified_retrieval.py` (Unified Retriever)
**Purpose:** Provides a single interface combining multiple retrieval strategies.

**Key Class:**
- `UnifiedRetriever` - Unified interface for all retrieval methods

**Supported Strategies:**
- Vector search (single-hop)
- Multi-hop retrieval
- Graph-RAG
- Symbol-driven ranking
- Reasoning chains

---

### `retrieval/graph.py` (Call Graph Visualization)
**Purpose:** Renders interactive call graph visualizations.

**Key Functions:**
- `render_call_graph()` - Create interactive vis.js network visualization
- Supports focus on specific symbols (with depth limit)
- Shows call relationships and hierarchies

---

### `retrieval/utils.py` (Retrieval Utilities)
**Purpose:** Common utility functions for retrieval module.

**Key Functions:**
- `rewrite_query_if_enabled()` - Optionally rewrite query for better search
- `summarize_chunk_heuristic()` - Generate brief summary of code chunk
- `chunk_title()` - Extract meaningful title from chunk
- `breadcrumb_for_path()` - Format file path as breadcrumbs
- `load_file_segment()` - Load surrounding code with padding
- `matched_terms_in_chunk()` - Find query terms in chunk

---

### `retrieval/onboarding/` (Onboarding Module)

#### `onboarding/analyzer.py`
**Purpose:** Analyzes codebase structure and generates insights for onboarding.

**Key Class:**
- `CodebaseAnalyzer` - Main analyzer class

**Key Functions:**
- `get_project_stats()` - Return project statistics (files, functions, complexity, etc.)
- `generate_project_summary()` - LLM-based project summary
- `get_entry_points()` - Identify main entry points and handlers
- `get_exit_points()` - Identify external calls and exit points
- `get_dependency_order()` - Topological order for understanding code
- `get_file_tree()` - Hierarchical file structure
- `get_weak_documentation_areas()` - Identify poorly documented code
- `explore_symbol()` - Get information about a specific symbol

---

#### `onboarding/visualization.py`
**Purpose:** Renders onboarding visualizations and UI components.

**Key Functions:**
- `render_project_overview()` - Display statistics and metrics
- `render_entry_exit_points()` - Show entry and exit points
- `render_roadmap()` - Display learning roadmap/dependency order
- `render_file_tree()` - Display hierarchical file structure
- `render_navigation_hints()` - Show symbol relationships and navigation
- `render_weak_documentation_section()` - Highlight undocumented code
- `render_summary()` - Display project summary

---

## 💪 CODE HEALTH MODULE (`code_health/`)

### `code_health/health_score.py` (Code Health Scoring)
**Purpose:** Calculates comprehensive code health scores (0-100).

**Core Class:**
- `HealthScoreCalculator` - Computes health metrics

**Metrics Calculated:**
- **Maintainability** (25%) - Complexity, function length, modularity
- **Modularity** (25%) - Cohesion, coupling, fan-out
- **Readability** (25%) - Comment ratio, naming quality
- **Change Risk** (15%) - Code churn, complexity trend
- **Dependency Hygiene** (10%) - Circular dependencies, import patterns

**Thresholds:**
- Complexity max: 15 (cyclomatic)
- Function length max: 50 lines
- Code churn max: 100
- Fan-out max: 20
- Comment ratio min: 10%

---

### `code_health/smells.py` (Code Smell Detection)
**Purpose:** Identifies code smells and anti-patterns.

**Detected Smells:**
- Long functions
- High cyclomatic complexity
- Large classes
- Duplicate code
- Deep nesting
- Long parameter lists
- High fan-out (too many dependencies)
- Circular dependencies

---

### `code_health/stats.py` (Code Statistics)
**Purpose:** Computes raw code statistics and metrics.

**Metrics:**
- Line counts (total, code, comments, blank)
- Function metrics (count, avg length, complexity)
- Class metrics (count, avg methods)
- Complexity metrics (cyclomatic, cognitive)
- Churn metrics (change frequency)
- Dependency metrics (imports, fan-in/fan-out)

---

### `code_health/refactoring.py` (Refactoring Suggestions)
**Purpose:** Suggests refactorings to improve code health.

**Types of Suggestions:**
- Extract function (break down long functions)
- Extract class (break down large classes)
- Reduce complexity (simplify conditionals)
- Remove duplication (consolidate similar code)
- Improve naming (rename unclear variables)
- Reduce coupling (decrease dependencies)

---

### `code_health/visualization.py` (Health Visualization)
**Purpose:** Renders code health visualizations and reports.

**Key Functions:**
- `render_code_health_tab()` - Main health tab display
- `render_health_score()` - Display overall health score
- `render_metrics_breakdown()` - Show metric composition
- `render_smells()` - List detected code smells
- `render_recommendations()` - Show refactoring suggestions
- `render_trend_chart()` - Show health trend over time

---

### `code_health/exporter.py` (Report Export)
**Purpose:** Exports code health reports in various formats.

**Export Formats:**
- JSON
- HTML
- CSV
- PDF (via HTML)

---

### `code_health/generate_report.py` (Report Generation)
**Purpose:** Generates comprehensive code health reports.

**Report Includes:**
- Summary statistics
- Health score breakdown
- Code smells detected
- Refactoring recommendations
- Top risk areas
- File-by-file analysis
- Trend analysis

---

### `code_health/test_integration.py` (Integration Tests)
**Purpose:** Tests for the code health module.

---

## 📚 DATA & STORAGE

### `data/` Directory
**Purpose:** Stores ingested repository analysis data.

**Structure per Repository:**
```
data/AskLegal.ai-AI-Legal-Assistant/
├── call_graph.json              # Function call relationships
├── dataflow_analysis.json       # Data flow information
├── knowledge_graph.json         # Semantic relationships
├── symbol_table.json            # All symbols in repository
└── vector_store/
    └── index.faiss              # FAISS vector index
```

---

### `repos/` Directory
**Purpose:** Stores cloned/ingested repository source code.

**Used For:**
- Displaying code snippets
- Computing file statistics
- Finding line numbers and surrounding context

---

## 🎨 LIBRARY & FRONTEND

### `lib/bindings/utils.js`
**Purpose:** JavaScript utilities for frontend integration.

---

### `lib/tom-select/`
**Purpose:** Tom Select - Lightweight dropdown/select plugin.

**Files:**
- `tom-select.complete.min.js` - Minified JavaScript
- `tom-select.css` - Styling

---

### `lib/vis-9.1.2/`
**Purpose:** Vis.js - Network visualization library for call graphs.

**Files:**
- `vis-network.min.js` - Minified JavaScript
- `vis-network.css` - Styling

---

## ⚙️ CONFIGURATION & DEPENDENCIES

### `requirements.txt`
**Purpose:** Python package dependencies.

**Key Dependencies:**
- **LLM**: `langchain`, `langchain-groq` (Groq API)
- **Embeddings**: `langchain-huggingface` (HuggingFace embeddings)
- **Vector DB**: `faiss-cpu` (Similarity search)
- **Web**: `streamlit` (UI framework)
- **Parsing**: `tree-sitter`, `tree-sitter-languages` (Code parsing)
- **Analysis**: `networkx` (Graph algorithms)
- **Utils**: `dotenv`, `numpy`, `pandas`

---

### `.env` (Configuration)
**Purpose:** Environment variables (not tracked in git).

**Required Variables:**
- `GROQ_API_KEY` - Groq API key for LLM
- `LANGCHAIN_API_KEY` - LangSmith API key (optional)
- `LANGCHAIN_TRACING_V2` - Enable LangSmith tracing (optional)

---

### `README.md`
**Purpose:** Project overview and setup instructions.

---

## 🔄 DATA FLOW OVERVIEW

### Ingestion Pipeline
```
Repository (GitHub URL or Local Path)
    ↓
ingest.py (orchestrator)
    ├→ callgraph.py (extract calls)
    ├→ symbols.py (extract symbols)
    ├→ chunking.py (split code)
    ├→ knowledge_graph.py (build KG)
    └→ cache.py (create FAISS index)
    ↓
data/{repo_name}/
├── call_graph.json
├── dataflow_analysis.json
├── knowledge_graph.json
├── symbol_table.json
└── vector_store/index.faiss
```

### Query Pipeline (Graph-RAG)
```
User Query (Streamlit UI)
    ↓
query_understanding.py (analyze intent)
    ↓
graph_rag.py (orchestrator)
    ├→ cache.py (load vectorstore)
    ├→ retrieval.py (vector search)
    ├→ graph_traversal.py (explore KG)
    ├→ deduplication
    └→ context building
    ↓
cache.py (get LLM)
    ↓
LLM (Groq) - Generate Answer
    ↓
app.py (Streamlit UI)
    ↓
Display Results & Sources
```

---

## 🎯 Key Design Patterns

### 1. **Caching Pattern**
- Expensive operations cached with `@st.cache_resource`
- Multi-repo support with `repo_name` parameter
- Cache invalidation on repo switch

### 2. **Multi-Parser Strategy**
- Try tree-sitter first (most robust)
- Fall back to AST (Python)
- Fall back to regex (all languages)

### 3. **Graph-RAG Architecture**
- Vector search finds initial anchor nodes
- Knowledge graph traversal expands context
- Deduplication removes redundant results
- LLM generates final answer

### 4. **Multi-Repository Support**
- Repository selection in UI
- Separate data directories per repo
- Cache invalidation on repo switch
- Dynamic path generation

### 5. **Modular Design**
- Ingestion independent from retrieval
- Retrieval strategies pluggable
- Analysis modules independent
- Utility functions centralized

---

## 📊 Default Configuration

**Current App Settings (Hardcoded):**
- **Retrieval Strategy**: Graph-RAG (Knowledge Graph + Vector Search)
- **Smart Query Rewrite**: Enabled
- **Graph Max Depth**: 4
- **Traversal Strategy**: DFS (Depth-First Search)
- **Edge Types**: calls, called_by, contains, dataflow
- **Deduplication**: Enabled

---

## 🚀 Usage Examples

### Running the Application
```bash
streamlit run retrieval/app.py
```

### Ingesting a Repository
1. Enter repository URL or local path
2. Click "Ingest" button
3. Wait for indexing to complete
4. Select repository from dropdown

### Asking Questions
1. Select repository
2. Enter question (e.g., "Where is judgment prediction implemented?")
3. Click "Run Query"
4. View AI answer and code matches

### Exploring Code Health
1. Go to "Code Health" tab in Onboarding section
2. View health score, metrics breakdown, and recommendations

---

## 📝 File Statistics

- **Total Python Files**: ~25+
- **Total Lines of Code**: ~8000+
- **Supported Languages**: Python, JavaScript, TypeScript, Java, C++, Go, Rust
- **Core Modules**: 5 (ingestion, retrieval, code_health, onboarding, cache)
- **Retrieval Strategies**: Vector Search, Multi-hop, Graph-RAG, Symbol-driven

---

## 🔗 Key Interactions

```
ingestion/ → data/ (outputs)
           → repos/ (source storage)

retrieval/ → cache.py (loads data/)
           → query_understanding.py (analyzes queries)
           → graph_rag.py (main strategy)
           → graph_traversal.py (explores KG)
           → retrieval.py (vector + reranking)

code_health/ → stats.py (computes metrics)
             → smells.py (detects issues)
             → health_score.py (scores health)
             → visualization.py (renders UI)

app.py → cache.py, retrieval/, code_health/
       → onboarding/ (analysis)
       → Uses all modules

onboarding/ → analyzer.py (analyzes codebase)
            → visualization.py (renders insights)
```

---

This documentation serves as a complete reference for understanding the architecture, purpose, and relationships between all components of the Chat With Codebase application.
