# symbol_driven_ranking.py
"""
Symbol-Driven Multi-Rank Retrieval Pipeline

Implements sophisticated ranking that:
1. Extracts and normalizes query keywords
2. Matches possible symbol names (exact, substring, semantic)
3. Resolves to fully qualified names via symbol table
4. Computes candidate sets from direct definitions, callees, callers, and support structures
5. Merges with vector-search results
6. Re-ranks using composite scoring: w1*symbol_match + w2*callgraph_distance + w3*locality + w4*embedding
7. Returns perfectly-ranked documents with direct implementation first
"""

import re
import json
import numpy as np
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict, deque
from difflib import SequenceMatcher
from langchain_core.documents import Document


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SymbolMatch:
    """Represents a symbol match from query keyword."""
    keyword: str
    fqn: str  # fully qualified name
    match_type: str  # "exact", "substring", "semantic"
    confidence: float  # 0.0 to 1.0
    file_path: str
    line_number: int
    kind: str  # "function", "class", "method", "variable"
    

@dataclass
class CandidateSymbol:
    """Represents a candidate symbol with ranking info."""
    fqn: str
    file_path: str
    line_number: int
    kind: str
    distance_from_query: int  # callgraph hops from matched symbol
    is_direct_match: bool  # matched directly from query
    related_callees: List[str] = None  # symbols this calls
    related_callers: List[str] = None  # symbols that call this
    support_symbols: List[str] = None  # class members, helpers
    
    def __post_init__(self):
        if self.related_callees is None:
            self.related_callees = []
        if self.related_callers is None:
            self.related_callers = []
        if self.support_symbols is None:
            self.support_symbols = []


# ============================================================================
# KEYWORD EXTRACTION & NORMALIZATION
# ============================================================================

class QueryKeywordExtractor:
    """Extract and normalize query keywords for symbol matching."""
    
    def __init__(self):
        # Simple stemmer - maps common suffixes to stems
        self.stem_rules = {
            'ing': '',
            'ed': '',
            'es': '',
            's': '',
            'er': '',
            'est': '',
            'ly': '',
        }
    
    def tokenize(self, query: str) -> List[str]:
        """Extract words from query."""
        # Match identifiers: camelCase, snake_case, PascalCase
        tokens = re.findall(r'[a-zA-Z_]\w*', query)
        return tokens
    
    def normalize(self, token: str) -> str:
        """Lowercase token."""
        return token.lower()
    
    def stem(self, word: str) -> str:
        """Simple rule-based stemming."""
        word_lower = word.lower()
        for suffix, replacement in self.stem_rules.items():
            if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 2:
                return word_lower[:-len(suffix)] + replacement
        return word_lower
    
    def extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """Extract keywords with variants: [original, normalized, stemmed]."""
        tokens = self.tokenize(query)
        keywords = {}
        
        for token in tokens:
            if len(token) > 2:  # ignore very short tokens
                normalized = self.normalize(token)
                stemmed = self.stem(token)
                keywords[token] = [token, normalized, stemmed]
        
        return keywords


# ============================================================================
# SYMBOL MATCHING
# ============================================================================

class SymbolMatcher:
    """Match query keywords to symbol names using multiple strategies."""
    
    def __init__(self, symbol_table: Dict[str, Any], embeddings=None):
        """
        Args:
            symbol_table: Symbol table JSON loaded from disk
            embeddings: Optional embedding model for semantic similarity
        """
        self.symbol_table = symbol_table or {}
        self.embeddings = embeddings
        self.global_symbols = self._build_global_symbol_index()
    
    def _build_global_symbol_index(self) -> Dict[str, List[Dict[str, Any]]]:
        """Build searchable index of all symbols."""
        index = defaultdict(list)
        
        if "global_index" not in self.symbol_table:
            return index
        
        global_index = self.symbol_table["global_index"]
        if "global_symbols" in global_index:
            for symbol_name, occurrences in global_index["global_symbols"].items():
                for occ in occurrences:
                    index[symbol_name.lower()].append(occ)
        
        return dict(index)
    
    def exact_match(self, keyword: str) -> List[SymbolMatch]:
        """Match keyword exactly to symbol names."""
        matches = []
        keyword_lower = keyword.lower()
        
        if keyword_lower in self.global_symbols:
            for sym in self.global_symbols[keyword_lower]:
                matches.append(SymbolMatch(
                    keyword=keyword,
                    fqn=sym.get("fqn", ""),
                    match_type="exact",
                    confidence=1.0,
                    file_path=sym.get("file", ""),
                    line_number=sym.get("line", 0),
                    kind=sym.get("kind", "unknown")
                ))
        
        return matches
    
    def substring_match(self, keyword: str, threshold: float = 0.6) -> List[SymbolMatch]:
        """Match keyword as substring in symbol names."""
        matches = []
        keyword_lower = keyword.lower()
        
        for symbol_name, occurrences in self.global_symbols.items():
            if keyword_lower in symbol_name:
                ratio = len(keyword_lower) / len(symbol_name)
                if ratio >= threshold:
                    for sym in occurrences:
                        matches.append(SymbolMatch(
                            keyword=keyword,
                            fqn=sym.get("fqn", ""),
                            match_type="substring",
                            confidence=ratio,
                            file_path=sym.get("file", ""),
                            line_number=sym.get("line", 0),
                            kind=sym.get("kind", "unknown")
                        ))
        
        return matches
    
    def semantic_match(self, keyword: str, top_k: int = 3) -> List[SymbolMatch]:
        """Match keyword using semantic similarity (if embeddings available)."""
        if self.embeddings is None:
            return []
        
        matches = []
        try:
            keyword_vec = self.embeddings.embed_query(keyword)
            keyword_vec = np.array(keyword_vec, dtype=float)
            keyword_norm = np.linalg.norm(keyword_vec) + 1e-8
            
            scored = []
            for symbol_name in self.global_symbols.keys():
                try:
                    sym_vec = self.embeddings.embed_query(symbol_name)
                    sym_vec = np.array(sym_vec, dtype=float)
                    sym_norm = np.linalg.norm(sym_vec) + 1e-8
                    
                    cosine = float(np.dot(keyword_vec, sym_vec) / (keyword_norm * sym_norm))
                    if cosine > 0.6:
                        scored.append((symbol_name, cosine))
                except Exception:
                    pass
            
            scored.sort(key=lambda x: x[1], reverse=True)
            
            for symbol_name, confidence in scored[:top_k]:
                for sym in self.global_symbols[symbol_name]:
                    matches.append(SymbolMatch(
                        keyword=keyword,
                        fqn=sym.get("fqn", ""),
                        match_type="semantic",
                        confidence=confidence,
                        file_path=sym.get("file", ""),
                        line_number=sym.get("line", 0),
                        kind=sym.get("kind", "unknown")
                    ))
        except Exception:
            pass
        
        return matches
    
    def match_keyword(self, keyword: str) -> List[SymbolMatch]:
        """Match keyword using all strategies and deduplicate."""
        all_matches = []
        
        # Try exact match first (highest priority)
        exact = self.exact_match(keyword)
        all_matches.extend(exact)
        
        # Substring match
        substring = self.substring_match(keyword)
        all_matches.extend(substring)
        
        # Semantic match
        semantic = self.semantic_match(keyword)
        all_matches.extend(semantic)
        
        # Deduplicate by FQN and keep highest confidence
        dedup = {}
        for match in all_matches:
            if match.fqn not in dedup or match.confidence > dedup[match.fqn].confidence:
                dedup[match.fqn] = match
        
        return list(dedup.values())


# ============================================================================
# CALL GRAPH ANALYSIS
# ============================================================================

class CallGraphAnalyzer:
    """Analyze call graph to find related symbols."""
    
    def __init__(self, call_graph: Dict[str, List[str]]):
        """
        Args:
            call_graph: Call graph dict mapping "file:function" -> [callees]
        """
        self.call_graph = call_graph or {}
        self.reverse_graph = self._build_reverse_graph()
    
    def _build_reverse_graph(self) -> Dict[str, Set[str]]:
        """Build reverse call graph: callee -> [callers]."""
        reverse = defaultdict(set)
        for caller, callees in self.call_graph.items():
            for callee in callees:
                reverse[callee].add(caller)
        return dict(reverse)
    
    def get_callees(self, fqn: str) -> List[str]:
        """Get all functions called by this FQN."""
        # Try exact match and partial matches
        if fqn in self.call_graph:
            return self.call_graph[fqn]
        
        # Try matching just the function name part
        callees = []
        for key, vals in self.call_graph.items():
            if key.endswith(fqn) or key.split(":")[-1] == fqn.split(":")[-1]:
                callees.extend(vals)
        
        return list(set(callees))
    
    def get_callers(self, fqn: str) -> List[str]:
        """Get all functions that call this FQN."""
        callers = []
        
        # Try exact match
        if fqn in self.reverse_graph:
            callers.extend(self.reverse_graph[fqn])
        
        # Try matching by function name
        for callee_key, caller_set in self.reverse_graph.items():
            if callee_key.endswith(fqn) or callee_key.split(":")[-1] == fqn.split(":")[-1]:
                callers.extend(caller_set)
        
        return list(set(callers))
    
    def bfs_neighbors(self, fqn: str, max_depth: int = 2) -> Dict[str, int]:
        """Get all reachable symbols within max_depth hops (BFS)."""
        neighbors = {fqn: 0}
        queue = deque([(fqn, 0)])
        
        while queue:
            current, depth = queue.popleft()
            
            if depth >= max_depth:
                continue
            
            # Add callees
            for callee in self.get_callees(current):
                if callee not in neighbors:
                    neighbors[callee] = depth + 1
                    queue.append((callee, depth + 1))
            
            # Add callers
            for caller in self.get_callers(current):
                if caller not in neighbors:
                    neighbors[caller] = depth + 1
                    queue.append((caller, depth + 1))
        
        return neighbors


# ============================================================================
# CANDIDATE SET COMPUTATION
# ============================================================================

class CandidateSetBuilder:
    """Build candidate set from matched symbols and call graph."""
    
    def __init__(self, symbol_table: Dict[str, Any], call_graph: Dict[str, List[str]],
                 symbol_matches: List[SymbolMatch], vector_candidates: List[Document]):
        self.symbol_table = symbol_table or {}
        self.call_graph_analyzer = CallGraphAnalyzer(call_graph)
        self.symbol_matches = symbol_matches
        self.vector_candidates = vector_candidates
    
    def build_candidates(self) -> Dict[str, CandidateSymbol]:
        """Build comprehensive candidate set."""
        candidates = {}
        
        # 1. Direct symbol matches from query
        for match in self.symbol_matches:
            if match.fqn not in candidates:
                candidates[match.fqn] = CandidateSymbol(
                    fqn=match.fqn,
                    file_path=match.file_path,
                    line_number=match.line_number,
                    kind=match.kind,
                    distance_from_query=0,
                    is_direct_match=True
                )
        
        # 2. Add callees and callers with distance tracking
        for match in self.symbol_matches:
            neighbors = self.call_graph_analyzer.bfs_neighbors(match.fqn, max_depth=2)
            
            for neighbor_fqn, distance in neighbors.items():
                if neighbor_fqn == match.fqn:
                    continue  # Skip self
                
                if neighbor_fqn not in candidates:
                    candidates[neighbor_fqn] = CandidateSymbol(
                        fqn=neighbor_fqn,
                        file_path="",  # Will be populated from vector candidates
                        line_number=0,
                        kind="function",
                        distance_from_query=distance,
                        is_direct_match=False
                    )
                else:
                    # Update distance to minimum
                    candidates[neighbor_fqn].distance_from_query = min(
                        candidates[neighbor_fqn].distance_from_query,
                        distance
                    )
        
        # 3. Populate file paths and line numbers from vector candidates
        fqn_to_doc = self._build_fqn_doc_map()
        for fqn, candidate in candidates.items():
            if fqn in fqn_to_doc:
                doc = fqn_to_doc[fqn]
                meta = doc.metadata or {}
                candidate.file_path = meta.get("path", "")
                candidate.line_number = meta.get("start_line", 0)
        
        return candidates
    
    def _build_fqn_doc_map(self) -> Dict[str, Document]:
        """Map FQN to vector candidate documents."""
        fqn_map = {}
        
        for doc in self.vector_candidates:
            meta = doc.metadata or {}
            path = meta.get("path", "")
            symbol = meta.get("symbol_name", "")
            
            if path and symbol:
                fqn = f"{path}:{symbol}"
                fqn_map[fqn] = doc
        
        return fqn_map


# ============================================================================
# RE-RANKING
# ============================================================================

class SymbolDrivenRanker:
    """Re-rank documents using symbol-aware multi-factor scoring."""
    
    def __init__(self, 
                 w_symbol: float = 0.35,
                 w_callgraph: float = 0.25,
                 w_locality: float = 0.15,
                 w_embedding: float = 0.25):
        """
        Args:
            w_symbol: Weight for symbol match score (0.35)
            w_callgraph: Weight for call graph distance (0.25)
            w_locality: Weight for code locality/organization (0.15)
            w_embedding: Weight for embedding similarity (0.25)
        """
        self.w_symbol = w_symbol
        self.w_callgraph = w_callgraph
        self.w_locality = w_locality
        self.w_embedding = w_embedding
    
    def score_symbol_match(self, candidate: CandidateSymbol, 
                          symbol_matches: List[SymbolMatch]) -> float:
        """Score based on symbol matching confidence."""
        if candidate.is_direct_match:
            # Direct matches get high scores
            max_conf = max([m.confidence for m in symbol_matches 
                           if m.fqn == candidate.fqn], default=0.8)
            return max_conf
        return 0.1  # Low score for indirect matches
    
    def score_callgraph_distance(self, candidate: CandidateSymbol) -> float:
        """Score based on proximity in call graph."""
        if candidate.is_direct_match:
            return 1.0
        
        distance = candidate.distance_from_query
        if distance <= 1:
            return 0.8
        elif distance <= 2:
            return 0.5
        else:
            return 0.2
    
    def score_locality(self, doc: Document, query: str) -> float:
        """Score based on code locality and organization."""
        meta = doc.metadata or {}
        path = (meta.get("path") or "").lower()
        node_type = (meta.get("node_type") or "").lower()
        
        score = 0.5  # Base score
        
        # Boost for function/class definitions
        if "function" in node_type or "class" in node_type:
            score += 0.2
        
        # Boost for main implementation files (not utils/helpers)
        if not any(part in path for part in ["test", "util", "helper", "lib", "vendor"]):
            score += 0.1
        
        # Boost if path contains query keywords
        q_tokens = set(re.findall(r"\w+", query.lower()))
        path_tokens = set(re.findall(r"\w+", path))
        if q_tokens & path_tokens:
            score += 0.15
        
        return min(score, 1.0)
    
    def score_embedding(self, doc: Document, vector_score: float) -> float:
        """Score based on embedding similarity."""
        # Vector score is typically distance (0 = perfect, higher = worse)
        # Convert to similarity: similarity = 1 / (1 + distance)
        return 1.0 / (1.0 + float(vector_score))
    
    def rank_documents(self, 
                      query: str,
                      candidates: Dict[str, CandidateSymbol],
                      vector_candidates: List[Tuple[Document, float]],
                      symbol_matches: List[SymbolMatch]) -> List[Document]:
        """
        Compute composite score and rank documents.
        
        Score = w1*symbol_match + w2*callgraph_distance + w3*locality + w4*embedding
        """
        # Build document map from vector candidates
        doc_map = {id(doc): (doc, score) for doc, score in vector_candidates}
        
        scored_docs = []
        
        for doc, vec_score in vector_candidates:
            meta = doc.metadata or {}
            path = meta.get("path", "")
            symbol = meta.get("symbol_name", "")
            fqn = f"{path}:{symbol}" if path and symbol else ""
            
            # Get candidate info if available
            candidate = candidates.get(fqn)
            
            # Calculate component scores
            if candidate:
                s_symbol = self.score_symbol_match(candidate, symbol_matches)
                s_callgraph = self.score_callgraph_distance(candidate)
            else:
                s_symbol = 0.0
                s_callgraph = 0.1
            
            s_locality = self.score_locality(doc, query)
            s_embedding = self.score_embedding(doc, vec_score)
            
            # Composite score
            total_score = (
                self.w_symbol * s_symbol +
                self.w_callgraph * s_callgraph +
                self.w_locality * s_locality +
                self.w_embedding * s_embedding
            )
            
            scored_docs.append((doc, total_score, {
                'symbol': s_symbol,
                'callgraph': s_callgraph,
                'locality': s_locality,
                'embedding': s_embedding,
                'total': total_score
            }))
        
        # Sort by total score (descending)
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return scored_docs


# ============================================================================
# MAIN API
# ============================================================================

def symbol_driven_multi_rank(query: str,
                            vector_candidates: List[Tuple[Document, float]],
                            symbol_table: Dict[str, Any],
                            call_graph: Dict[str, List[str]],
                            embeddings=None,
                            top_k: int = 6,
                            verbose: bool = True) -> List[Document]:
    """
    Symbol-driven multi-rank retrieval pipeline.
    
    Flow:
    1. Extract query keywords (lowercase, split, stem)
    2. Match possible symbol names using:
       - exact match
       - substring match
       - semantic similarity
    3. Resolve matching symbols to their fully qualified names
    4. Compute a candidate set:
       a. direct symbol definitions
       b. their callees from call_graph
       c. their callers from call_graph
       d. supporting classes and methods from symbol table
    5. Merge these candidates into the existing vector-search results
    6. Re-rank using:
       score = w1*symbol_match + w2*callgraph_distance + w3*locality + w4*embedding
    7. Final result shows:
       - direct implementation function first
       - its helpers next
       - support structures next
       - NO unrelated files
    
    Args:
        query: User query string
        vector_candidates: List of (Document, similarity_score) from vector search
        symbol_table: Loaded symbol table JSON
        call_graph: Loaded call graph JSON
        embeddings: Optional embedding model for semantic matching
        top_k: Number of top results to return
        verbose: Print debug info
    
    Returns:
        List of Documents ranked by symbol-driven scoring
    """
    if verbose:
        print(f"🔮 Symbol-Driven Multi-Rank Pipeline")
        print(f"   Query: {query!r}")
        print(f"   Vector candidates: {len(vector_candidates)}")
    
    # Step 1: Extract and normalize query keywords
    extractor = QueryKeywordExtractor()
    keywords_dict = extractor.extract_keywords(query)
    
    if verbose:
        print(f"   Keywords extracted: {list(keywords_dict.keys())}")
    
    # Step 2: Match symbols
    matcher = SymbolMatcher(symbol_table, embeddings)
    all_matches = []
    
    for keyword in keywords_dict.keys():
        matches = matcher.match_keyword(keyword)
        all_matches.extend(matches)
        if verbose and matches:
            print(f"   ✓ Matched '{keyword}' -> {len(matches)} symbols")
    
    # Deduplicate matches
    matches_by_fqn = {}
    for match in all_matches:
        if match.fqn not in matches_by_fqn:
            matches_by_fqn[match.fqn] = match
    all_matches = list(matches_by_fqn.values())
    
    if verbose:
        print(f"   Total unique matches: {len(all_matches)}")
    
    # Step 3-4: Build candidate set
    builder = CandidateSetBuilder(symbol_table, call_graph, all_matches, 
                                 [doc for doc, _ in vector_candidates])
    candidates = builder.build_candidates()
    
    if verbose:
        direct = sum(1 for c in candidates.values() if c.is_direct_match)
        print(f"   Candidate set: {len(candidates)} symbols ({direct} direct)")
    
    # Step 5: Merge with vector results (already done via builder)
    
    # Step 6-7: Re-rank documents
    ranker = SymbolDrivenRanker()
    scored_docs = ranker.rank_documents(query, candidates, vector_candidates, all_matches)
    
    # Filter and return top results
    # Prefer direct matches first, then by score
    direct_matches = [d for d, s, _ in scored_docs if candidates.get(
        f"{d.metadata.get('path', '')}:{d.metadata.get('symbol_name', '')}"
    ) and candidates[
        f"{d.metadata.get('path', '')}:{d.metadata.get('symbol_name', '')}"
    ].is_direct_match]
    
    remaining = [d for d, s, _ in scored_docs if d not in direct_matches]
    
    final_ranking = direct_matches[:2] + remaining[:top_k - len(direct_matches)]
    
    if verbose:
        print(f"   Final ranking ({len(final_ranking)} docs):")
        for i, doc in enumerate(final_ranking, 1):
            meta = doc.metadata or {}
            print(f"     {i}. {meta.get('path', '?')} : {meta.get('symbol_name', '?')}")
    
    return final_ranking