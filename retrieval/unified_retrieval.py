# unified_retrieval.py
"""
Unified advanced retrieval system integrating:

1. MULTI-SIMILARITY RETRIEVAL (from retriever.py)
   - Function signature similarity
   - Control flow pattern matching
   - Import/dependency similarity
   - API call pattern matching

2. HYBRID ADVANCED RETRIEVAL (from advanced_retrieval.py)
   - Global symbol index + cross-file reference resolution
   - Hybrid embedding + structural scoring fusion
   - Call graph neighborhood expansion
   - Data-flow & CFG information in retrieval scoring

This is the definitive unified retrieval system with all features integrated.
"""

import re
import json
import math
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from difflib import SequenceMatcher
from langchain_core.documents import Document
import numpy as np


# ============================================================================
# PART 1: DATA STRUCTURES & CORE EXTRACTORS
# ============================================================================

@dataclass
class CodeSignature:
    """Extracted function signature information."""
    name: str
    params: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    
    def to_string(self) -> str:
        """Convert signature to comparable string."""
        parts = []
        if self.decorators:
            parts.append(",".join(self.decorators))
        if self.is_async:
            parts.append("async")
        parts.append(f"{self.name}({','.join(self.params)})")
        if self.return_type:
            parts.append(f"->{self.return_type}")
        return " ".join(parts)


@dataclass
class CodeControlFlow:
    """Extracted control flow information."""
    branches: List[str] = field(default_factory=list)
    loops: int = 0
    conditionals: int = 0
    exception_handling: bool = False
    early_returns: int = 0
    
    def to_string(self) -> str:
        """Convert control flow to comparable string."""
        parts = [f"loops:{self.loops}", f"conds:{self.conditionals}"]
        if self.exception_handling:
            parts.append("try/except")
        if self.early_returns > 0:
            parts.append(f"returns:{self.early_returns}")
        return "|".join(parts)


@dataclass
class CodeImports:
    """Extracted import information."""
    imports: Set[str] = field(default_factory=set)
    aliases: Dict[str, str] = field(default_factory=dict)
    
    def to_string(self) -> str:
        """Convert imports to comparable string."""
        sorted_imports = sorted(self.imports)
        return ",".join(sorted_imports)


@dataclass
class APICall:
    """Represents an API/function call."""
    name: str
    module: Optional[str] = None
    is_method: bool = False
    arg_count: int = 0
    
    def to_string(self) -> str:
        """Convert API call to comparable string."""
        if self.module:
            return f"{self.module}.{self.name}"
        return self.name


@dataclass
class SymbolRef:
    """Cross-file symbol reference information."""
    name: str
    file_path: str
    line_number: int
    kind: str
    confidence: float = 0.5
    fully_qualified_name: Optional[str] = None
    related_symbols: List[str] = field(default_factory=list)


# ============================================================================
# PART 2: CODE METRICS EXTRACTION
# ============================================================================

class CodeMetricsExtractor:
    """Extract various code metrics from source text."""
    
    @staticmethod
    def extract_signature(chunk_text: str, metadata: Dict[str, Any]) -> CodeSignature:
        """Extract function signature from chunk metadata and text."""
        sig = CodeSignature(
            name=metadata.get("symbol_name") or "unknown",
            params=metadata.get("params") or [],
            decorators=metadata.get("decorators") or [],
        )
        
        if "async" in chunk_text[:100]:
            sig.is_async = True
        
        if metadata.get("parent_class"):
            sig.is_method = True
        
        return sig
    
    @staticmethod
    def extract_control_flow(chunk_text: str) -> CodeControlFlow:
        """Extract control flow patterns from source code."""
        cf = CodeControlFlow()
        lines = chunk_text.split("\n")
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith("if ") or stripped.startswith("elif "):
                cf.conditionals += 1
                cf.branches.append("if")
            elif stripped.startswith("else"):
                cf.branches.append("else")
            
            if stripped.startswith("for ") or stripped.startswith("while "):
                cf.loops += 1
                cf.branches.append("loop")
            
            if "try:" in stripped or "except " in stripped or "finally:" in stripped:
                cf.exception_handling = True
            
            if stripped.startswith("return "):
                cf.early_returns += 1
        
        return cf
    
    @staticmethod
    def extract_imports(chunk_text: str, metadata: Dict[str, Any]) -> CodeImports:
        """Extract import statements from chunk."""
        imports = CodeImports()
        
        meta_imports = metadata.get("imports") or []
        for imp in meta_imports:
            if imp:
                if " import " in imp:
                    parts = imp.split(" import ")
                    module = parts[0].replace("from ", "").strip()
                    names = parts[1].split(",") if len(parts) > 1 else []
                    for name in names:
                        imports.imports.add(f"{module}.{name.strip()}")
                else:
                    names = imp.replace("import ", "").split(",")
                    for name in names:
                        imports.imports.add(name.strip())
        
        import_patterns = [
            r'^import\s+([\w\.]+(?:\s+as\s+\w+)?)',
            r'^from\s+([\w\.]+)\s+import\s+([\w\s,]+)',
        ]
        
        for line in chunk_text.split("\n"):
            stripped = line.strip()
            for pattern in import_patterns:
                matches = re.findall(pattern, stripped)
                for match in matches:
                    if isinstance(match, tuple):
                        module = match[0]
                        imports.imports.add(module)
                    else:
                        imports.imports.add(match)
        
        return imports
    
    @staticmethod
    def extract_api_calls(chunk_text: str) -> List[APICall]:
        """Extract function/method calls from source code."""
        calls = []
        call_pattern = r'(\w+)\.(\w+)\s*\(|(\w+)\s*\('
        
        for match in re.finditer(call_pattern, chunk_text):
            if match.group(1) and match.group(2):
                module = match.group(1)
                name = match.group(2)
                calls.append(APICall(name=name, module=module, is_method=True))
            elif match.group(3):
                name = match.group(3)
                calls.append(APICall(name=name))
        
        return calls


# ============================================================================
# PART 3: SIMILARITY SCORING
# ============================================================================

class SimilarityScorer:
    """Compute similarity scores between code chunks."""
    
    @staticmethod
    def signature_similarity(sig1: CodeSignature, sig2: CodeSignature) -> float:
        """Compute similarity between two function signatures."""
        score = 0.0
        total_weight = 0.0
        
        # Name similarity (40% weight)
        name_sim = SequenceMatcher(None, sig1.name, sig2.name).ratio()
        score += name_sim * 0.4
        total_weight += 0.4
        
        # Param count similarity (20% weight)
        param_diff = abs(len(sig1.params) - len(sig2.params))
        max_params = max(len(sig1.params), len(sig2.params))
        param_sim = 1.0 - (param_diff / max(max_params, 1))
        score += param_sim * 0.2
        total_weight += 0.2
        
        # Decorator similarity (15% weight)
        if sig1.decorators and sig2.decorators:
            common_decs = len(set(sig1.decorators) & set(sig2.decorators))
            total_decs = max(len(sig1.decorators), len(sig2.decorators))
            dec_sim = common_decs / total_decs if total_decs > 0 else 0
        else:
            dec_sim = 1.0 if (len(sig1.decorators) == 0) == (len(sig2.decorators) == 0) else 0
        score += dec_sim * 0.15
        total_weight += 0.15
        
        # Async/method status (10% weight each)
        async_match = 1.0 if sig1.is_async == sig2.is_async else 0.0
        method_match = 1.0 if sig1.is_method == sig2.is_method else 0.0
        score += (async_match * 0.1) + (method_match * 0.1)
        total_weight += 0.2
        
        return score / total_weight if total_weight > 0 else 0.0
    
    @staticmethod
    def control_flow_similarity(cf1: CodeControlFlow, cf2: CodeControlFlow) -> float:
        """Compute similarity between control flow patterns."""
        score = 0.0
        
        # Loop count similarity
        loop_diff = abs(cf1.loops - cf2.loops)
        loop_sim = 1.0 - min(loop_diff / max(cf1.loops, cf2.loops, 1), 1.0)
        score += loop_sim * 0.3
        
        # Conditional count similarity
        cond_diff = abs(cf1.conditionals - cf2.conditionals)
        cond_sim = 1.0 - min(cond_diff / max(cf1.conditionals, cf2.conditionals, 1), 1.0)
        score += cond_sim * 0.3
        
        # Exception handling match
        except_match = 1.0 if cf1.exception_handling == cf2.exception_handling else 0.5
        score += except_match * 0.2
        
        # Early returns similarity
        ret_diff = abs(cf1.early_returns - cf2.early_returns)
        ret_sim = 1.0 - min(ret_diff / max(cf1.early_returns, cf2.early_returns, 1), 1.0)
        score += ret_sim * 0.2
        
        return score / 1.0
    
    @staticmethod
    def import_similarity(imports1: CodeImports, imports2: CodeImports) -> float:
        """Compute Jaccard similarity between import statements."""
        if not imports1.imports and not imports2.imports:
            return 1.0
        
        intersection = len(imports1.imports & imports2.imports)
        union = len(imports1.imports | imports2.imports)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    @staticmethod
    def api_call_similarity(calls1: List[APICall], calls2: List[APICall]) -> float:
        """Compute similarity between API call patterns."""
        if not calls1 and not calls2:
            return 1.0
        
        if not calls1 or not calls2:
            return 0.0
        
        sig1 = {(c.module or "builtin", c.name, c.is_method) for c in calls1}
        sig2 = {(c.module or "builtin", c.name, c.is_method) for c in calls2}
        
        intersection = len(sig1 & sig2)
        union = len(sig1 | sig2)
        
        if union == 0:
            return 0.0
        
        return intersection / union


# ============================================================================
# PART 4: GLOBAL SYMBOL INDEX (CROSS-FILE RESOLUTION)
# ============================================================================

class GlobalSymbolIndex:
    """Global index for fast symbol resolution across all files."""
    
    def __init__(self, symbol_table_data: Dict[str, Any]):
        """Initialize global symbol index from symbol table data."""
        self.symbol_table_data = symbol_table_data
        self.global_index = symbol_table_data.get('global_index', {})
        self.file_symbols = symbol_table_data.get('file_symbols', {})
        self._build_indexes()
    
    def _build_indexes(self):
        """Build fast lookup indexes."""
        self.symbols_by_name: Dict[str, List[SymbolRef]] = defaultdict(list)
        self.symbols_by_file: Dict[str, List[SymbolRef]] = defaultdict(list)
        self.fqn_to_symbol: Dict[str, SymbolRef] = {}
        
        for name, symbols in self.global_index.get('global_symbols', {}).items():
            for sym_info in symbols:
                ref = SymbolRef(
                    name=name,
                    file_path=sym_info.get('file', ''),
                    line_number=sym_info.get('line', 0),
                    kind=sym_info.get('kind', 'unknown'),
                    fully_qualified_name=sym_info.get('fqn')
                )
                self.symbols_by_name[name].append(ref)
                self.symbols_by_file[ref.file_path].append(ref)
                if ref.fully_qualified_name:
                    self.fqn_to_symbol[ref.fully_qualified_name] = ref
    
    def resolve_symbol(self, name: str, context_file: Optional[str] = None) -> Optional[SymbolRef]:
        """Resolve a symbol in context (prefer current file, then global)."""
        candidates = self.symbols_by_name.get(name, [])
        
        if not candidates:
            return None
        
        if context_file:
            for ref in candidates:
                if ref.file_path == context_file:
                    return ref
        
        return candidates[0]
    
    def find_references(self, symbol_name: str) -> List[SymbolRef]:
        """Find all references to a symbol across files."""
        references = self.global_index.get('references', {})
        referencing_fqns = references.get(symbol_name, [])
        
        results = []
        for fqn in referencing_fqns:
            if fqn in self.fqn_to_symbol:
                results.append(self.fqn_to_symbol[fqn])
        
        return results
    
    def get_file_symbols(self, file_path: str) -> List[SymbolRef]:
        """Get all symbols in a file."""
        return self.symbols_by_file.get(file_path, [])


# ============================================================================
# PART 5: DATA FLOW & CONTROL FLOW SCORING
# ============================================================================

class DataFlowScorer:
    """Scores chunks based on data flow and control flow patterns."""
    
    def __init__(self, dataflow_data: Dict[str, Dict[str, Any]]):
        """Initialize with data flow analysis results."""
        self.dataflow_data = dataflow_data or {}
        self._build_indexes()
    
    def _build_indexes(self):
        """Build indexes for fast lookup."""
        self.functions_by_file: Dict[str, List[str]] = defaultdict(list)
        self.defs_by_function: Dict[str, Dict[str, List[Dict]]] = {}
        self.control_flows_by_function: Dict[str, List[Dict]] = {}
        
        for file_path, functions in self.dataflow_data.items():
            for func_name, analysis in functions.items():
                func_id = f"{file_path}:{func_name}"
                
                self.functions_by_file[file_path].append(func_name)
                self.defs_by_function[func_id] = analysis.get('definitions', {})
                
                cf = analysis.get('control_flow', {})
                self.control_flows_by_function[func_id] = cf.get('branches', [])
    
    def score_data_flow_relevance(self, query_symbols: List[str], 
                                  chunk_symbols: List[str]) -> float:
        """Score relevance based on def-use relationships."""
        if not query_symbols or not chunk_symbols:
            return 0.0
        
        score = 0.0
        matches = 0
        
        for query_sym in query_symbols:
            for chunk_sym in chunk_symbols:
                if self._same_type(query_sym, chunk_sym):
                    score += 0.3
                    matches += 1
        
        if matches == 0:
            return 0.0
        
        return min(1.0, score / (len(query_symbols) * len(chunk_symbols)))
    
    def _same_type(self, sym1: str, sym2: str) -> bool:
        """Check if two symbols have the same inferred type."""
        type1 = self._get_type(sym1)
        type2 = self._get_type(sym2)
        
        return type1 and type2 and type1 == type2
    
    def _get_type(self, sym: str) -> Optional[str]:
        """Get inferred type of a symbol from any function analysis."""
        for func_id, defs in self.defs_by_function.items():
            for var_name, def_list in defs.items():
                if sym in var_name or var_name in sym:
                    if def_list and isinstance(def_list, list):
                        return def_list[0].get('type')
        
        return None
    
    def score_control_flow_complexity(self, file_path: str, func_name: str) -> float:
        """Score based on control flow complexity."""
        func_id = f"{file_path}:{func_name}"
        branches = self.control_flows_by_function.get(func_id, [])
        
        if not branches:
            return 0.5
        
        score = 0.5
        loop_count = sum(1 for b in branches if b.get('type') in ['for', 'while'])
        cond_count = sum(1 for b in branches if b.get('type') == 'if')
        
        score += min(0.3, loop_count * 0.1)
        score += min(0.2, cond_count * 0.05)
        
        return min(1.0, score)


# ============================================================================
# PART 6: CALL GRAPH EXPANSION
# ============================================================================

class CallGraphExpander:
    """Expands retrieval using call graph neighborhoods."""
    
    def __init__(self, call_graph_data: Dict[str, List[str]]):
        """Initialize with call graph data."""
        self.call_graph = call_graph_data or {}
        self._build_indexes()
    
    def _build_indexes(self):
        """Build reverse and forward indexes."""
        self.callees_by_caller: Dict[str, Set[str]] = {}
        self.callers_by_callee: Dict[str, Set[str]] = defaultdict(set)
        
        for caller, callees in self.call_graph.items():
            self.callees_by_caller[caller] = set(callees)
            for callee in callees:
                self.callers_by_callee[callee].add(caller)
    
    def get_call_neighborhood(self, symbol: str, depth: int = 2, 
                            direction: str = 'both') -> Dict[str, List[str]]:
        """Get call graph neighborhood around a symbol."""
        neighborhood = defaultdict(list)
        visited = set()
        
        def _traverse(node: str, current_depth: int, is_forward: bool):
            if current_depth > depth or node in visited:
                return
            
            visited.add(node)
            
            if is_forward or direction == 'both':
                callees = self.callees_by_caller.get(node, set())
                for callee in callees:
                    neighborhood[node].append(callee)
                    if current_depth < depth:
                        _traverse(callee, current_depth + 1, True)
            
            if not is_forward or direction == 'both':
                callers = self.callers_by_callee.get(node, set())
                for caller in callers:
                    neighborhood[node].append(caller)
                    if current_depth < depth:
                        _traverse(caller, current_depth + 1, False)
        
        _traverse(symbol, 0, direction in ['forward', 'both'])
        return dict(neighborhood)
    
    def score_call_proximity(self, symbol1: str, symbol2: str) -> float:
        """Score based on call graph distance (closer = higher score)."""
        distance = self._get_call_distance(symbol1, symbol2)
        
        if distance is None:
            return 0.0
        
        if distance == 0:
            return 1.0
        
        return math.exp(-distance * 0.5)
    
    def _get_call_distance(self, from_sym: str, to_sym: str) -> Optional[int]:
        """Get shortest call path distance between two symbols."""
        if from_sym == to_sym:
            return 0
        
        visited = {from_sym}
        queue = [(from_sym, 0)]
        
        while queue:
            current, dist = queue.pop(0)
            
            for callee in self.callees_by_caller.get(current, set()):
                if callee == to_sym:
                    return dist + 1
                if callee not in visited:
                    visited.add(callee)
                    queue.append((callee, dist + 1))
            
            for caller in self.callers_by_callee.get(current, set()):
                if caller == to_sym:
                    return dist + 1
                if caller not in visited:
                    visited.add(caller)
                    queue.append((caller, dist + 1))
        
        return None


# ============================================================================
# PART 7: UNIFIED RETRIEVER
# ============================================================================

class UnifiedRetriever:
    """
    Ultimate unified retriever combining:
    - Multi-similarity retrieval (signatures, control flow, imports, API calls)
    - Global symbol index with cross-file resolution
    - Hybrid embedding + structural scoring
    - Call graph neighborhood expansion
    - Data flow & CFG information
    """
    
    def __init__(self, vectorstore, symbol_table_data: Optional[Dict] = None,
                 dataflow_data: Optional[Dict] = None, 
                 call_graph_data: Optional[Dict] = None,
                 all_documents: Optional[List[Document]] = None):
        """
        Initialize unified retriever.
        
        Args:
            vectorstore: FAISS vectorstore
            symbol_table_data: Data from symbol_table.json
            dataflow_data: Data from dataflow_analysis.json
            call_graph_data: Data from call_graph.json
            all_documents: List of all document chunks
        """
        self.vectorstore = vectorstore
        self.all_documents = all_documents or []
        self.extractor = CodeMetricsExtractor()
        self.scorer = SimilarityScorer()
        
        # Initialize optional components
        self.symbol_index = GlobalSymbolIndex(symbol_table_data) if symbol_table_data else None
        self.dataflow_scorer = DataFlowScorer(dataflow_data) if dataflow_data else None
        self.call_graph_expander = CallGraphExpander(call_graph_data) if call_graph_data else None
        
        # Pre-compute metrics for all documents
        self.doc_metrics = {}
        self._precompute_metrics()
        
        # Build document indexes
        self._build_document_index()
    
    def _precompute_metrics(self):
        """Pre-compute code metrics for all documents."""
        for i, doc in enumerate(self.all_documents):
            try:
                metrics = {
                    "signature": self.extractor.extract_signature(
                        doc.page_content, doc.metadata or {}
                    ),
                    "control_flow": self.extractor.extract_control_flow(doc.page_content),
                    "imports": self.extractor.extract_imports(
                        doc.page_content, doc.metadata or {}
                    ),
                    "api_calls": self.extractor.extract_api_calls(doc.page_content),
                }
                self.doc_metrics[i] = metrics
            except Exception as e:
                self.doc_metrics[i] = None
    
    def _build_document_index(self):
        """Build indexes for fast document lookup."""
        self.docs_by_symbol: Dict[str, List[int]] = defaultdict(list)
        self.docs_by_file: Dict[str, List[int]] = defaultdict(list)
        
        for i, doc in enumerate(self.all_documents):
            meta = doc.metadata or {}
            
            if meta.get('symbol_name'):
                self.docs_by_symbol[meta['symbol_name']].append(i)
            
            if meta.get('path'):
                self.docs_by_file[meta['path']].append(i)
    
    def retrieve_unified(self, query: str, k: int = 10,
                        weights: Optional[Dict[str, float]] = None) -> List[Document]:
        """
        Unified retrieval combining all scoring methods.
        
        Args:
            query: Query string
            k: Number of results
            weights: Optional custom weights for each scoring method
        
        Returns:
            List of top-k documents
        """
        if weights is None:
            weights = {
                "semantic": 0.25,
                "signature": 0.15,
                "control_flow": 0.15,
                "imports": 0.10,
                "api_calls": 0.15,
                "symbol": 0.10,
                "callgraph": 0.10,
            }
        
        # Normalize weights
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}
        
        # Extract query symbols and context
        query_symbols = self._extract_symbols(query)
        query_doc = Document(page_content=query, metadata={})
        
        # Get query metrics
        query_sig = self.extractor.extract_signature(query, {})
        query_cf = self.extractor.extract_control_flow(query)
        query_imports = self.extractor.extract_imports(query, {})
        query_calls = self.extractor.extract_api_calls(query)
        
        # Get semantic results for anchoring
        try:
            semantic_results = self.vectorstore.similarity_search_with_score(query, k=k*3)
        except Exception:
            semantic_results = []
        
        # Score all documents
        doc_scores = defaultdict(float)
        doc_list = []
        
        for i, doc in enumerate(self.all_documents):
            meta = doc.metadata or {}
            doc_key = id(doc)
            doc_list.append((doc_key, doc))
            
            if i not in self.doc_metrics or self.doc_metrics[i] is None:
                continue
            
            metrics = self.doc_metrics[i]
            
            # 1. Semantic similarity
            semantic_score = self._get_semantic_score(doc, semantic_results)
            doc_scores[doc_key] += semantic_score * weights.get("semantic", 0)
            
            # 2. Signature similarity
            sig_score = self.scorer.signature_similarity(query_sig, metrics["signature"])
            doc_scores[doc_key] += sig_score * weights.get("signature", 0)
            
            # 3. Control flow similarity
            cf_score = self.scorer.control_flow_similarity(query_cf, metrics["control_flow"])
            doc_scores[doc_key] += cf_score * weights.get("control_flow", 0)
            
            # 4. Import similarity
            import_score = self.scorer.import_similarity(query_imports, metrics["imports"])
            doc_scores[doc_key] += import_score * weights.get("imports", 0)
            
            # 5. API call similarity
            api_score = self.scorer.api_call_similarity(query_calls, metrics["api_calls"])
            doc_scores[doc_key] += api_score * weights.get("api_calls", 0)
            
            # 6. Symbol relevance
            if self.symbol_index:
                symbol_score = self._score_symbol_relevance(
                    query_symbols, meta.get('symbol_name'), meta.get('path')
                )
                doc_scores[doc_key] += symbol_score * weights.get("symbol", 0)
            
            # 7. Call graph relevance
            if self.call_graph_expander:
                callgraph_score = self._score_callgraph_relevance(
                    query_symbols, meta.get('symbol_name')
                )
                doc_scores[doc_key] += callgraph_score * weights.get("callgraph", 0)
        
        # Sort and return top-k
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for doc_key, score in sorted_docs[:k]:
            for key, doc in doc_list:
                if key == doc_key:
                    results.append(doc)
                    break
        
        return results
    
    def _extract_symbols(self, query: str) -> List[str]:
        """Extract symbol names from query."""
        pattern = r'\b([a-zA-Z_]\w*)\b'
        matches = re.findall(pattern, query)
        
        common_words = {
            'find', 'show', 'get', 'the', 'is', 'are', 'and', 'or', 'where',
            'how', 'what', 'in', 'from', 'to', 'for', 'function', 'class', 'method'
        }
        
        return [m for m in matches if m.lower() not in common_words and len(m) > 2]
    
    def _get_semantic_score(self, doc: Document, semantic_results: List) -> float:
        """Get semantic similarity score for a document."""
        for result_doc, score in semantic_results:
            if id(result_doc) == id(doc):
                return 1.0 - score
        
        return 0.0
    
    def _score_symbol_relevance(self, query_symbols: List[str], 
                               chunk_symbol: Optional[str], 
                               chunk_file: Optional[str]) -> float:
        """Score based on symbol matching and resolution."""
        if not query_symbols or not chunk_symbol or not self.symbol_index:
            return 0.0
        
        score = 0.0
        
        for q_sym in query_symbols:
            if q_sym.lower() == chunk_symbol.lower():
                return 1.0
            
            if q_sym.lower() in chunk_symbol.lower():
                score += 0.5
            
            # Resolve via symbol index
            ref = self.symbol_index.resolve_symbol(q_sym, chunk_file)
            if ref and ref.name == chunk_symbol:
                score = max(score, 0.8)
        
        return min(1.0, score / max(len(query_symbols), 1))
    
    def _score_callgraph_relevance(self, query_symbols: List[str],
                                  chunk_symbol: Optional[str]) -> float:
        """Score based on call graph relationships."""
        if not query_symbols or not chunk_symbol or not self.call_graph_expander:
            return 0.0
        
        score = 0.0
        
        for q_sym in query_symbols:
            proximity = self.call_graph_expander.score_call_proximity(q_sym, chunk_symbol)
            score += proximity
        
        return min(1.0, score / max(len(query_symbols), 1))
