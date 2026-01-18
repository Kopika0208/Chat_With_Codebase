# query_understanding.py
"""
Advanced query understanding system with:
1. Structure-aware analysis - understand query intent and structure
2. Symbol-aware parsing - identify symbols and their properties
3. KG-aware expansion - leverage knowledge graph for context
"""

import re
import ast
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum


class QueryIntentType(Enum):
    """Types of query intents."""
    FIND_FUNCTION = "find_function"
    FIND_CLASS = "find_class"
    FIND_PATTERN = "find_pattern"
    FIND_USAGE = "find_usage"
    FIND_IMPLEMENTATION = "find_implementation"
    FIND_CALLER = "find_caller"
    FIND_RELATED = "find_related"
    UNDERSTAND_FLOW = "understand_flow"
    FIND_SIMILAR = "find_similar"
    CUSTOM = "custom"


class SymbolType(Enum):
    """Types of code symbols."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    MODULE = "module"
    ATTRIBUTE = "attribute"
    PARAMETER = "parameter"
    DECORATOR = "decorator"
    IMPORT = "import"
    CONSTANT = "constant"


@dataclass
class Symbol:
    """Represents an identified symbol in a query."""
    name: str
    type: SymbolType
    confidence: float  # 0.0-1.0
    context: str = ""  # surrounding context
    line_number: Optional[int] = None
    file_path: Optional[str] = None
    related_symbols: List[str] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, Symbol):
            return self.name == other.name and self.type == other.type
        return False


@dataclass
class QueryStructure:
    """Parsed structure of a user query."""
    original_query: str
    intent: QueryIntentType
    primary_symbols: List[Symbol] = field(default_factory=list)
    secondary_symbols: List[Symbol] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    keywords: Set[str] = field(default_factory=set)
    code_snippets: List[str] = field(default_factory=list)
    natural_language: str = ""
    
    def get_all_symbols(self) -> List[Symbol]:
        """Get all identified symbols."""
        return self.primary_symbols + self.secondary_symbols
    
    def has_code_snippet(self) -> bool:
        """Check if query contains code."""
        return len(self.code_snippets) > 0


class StructureAwareAnalyzer:
    """Analyzes query structure and intent."""
    
    # Intent patterns
    INTENT_PATTERNS = {
        QueryIntentType.FIND_FUNCTION: [
            r'find\s+(?:the\s+)?(?:function|def)\s+(\w+)',
            r'(?:function|def)\s+(\w+)',
            r'show\s+(?:me\s+)?(?:function|def)\s+(\w+)',
            r'(?:how|what|where)\s+(?:is|are)\s+(?:the\s+)?(?:function|def)\s+(\w+)',
        ],
        QueryIntentType.FIND_CLASS: [
            r'find\s+(?:the\s+)?(?:class|type)\s+(\w+)',
            r'(?:class|type)\s+(\w+)',
            r'show\s+(?:me\s+)?(?:class|type)\s+(\w+)',
            r'(?:how|what|where)\s+(?:is|are)\s+(?:the\s+)?(?:class|type)\s+(\w+)',
        ],
        QueryIntentType.FIND_USAGE: [
            r'(?:where|how)\s+(?:is\s+)?(\w+)\s+(?:used|called)',
            r'find\s+(?:all\s+)?(?:usages?|calls?|references?)\s+(?:to\s+)?(\w+)',
            r'who\s+(?:calls?|uses?)\s+(\w+)',
        ],
        QueryIntentType.FIND_CALLER: [
            r'(?:what|which)\s+(?:function|method)\s+(?:calls?|invokes?)\s+(\w+)',
            r'find\s+(?:callers?|callee|references?)\s+(?:of|to)\s+(\w+)',
            r'(?:who|what)\s+calls?\s+(\w+)',
        ],
        QueryIntentType.FIND_IMPLEMENTATION: [
            r'(?:show|find|implement)\s+(?:me\s+)?(?:the\s+)?implementation\s+(?:of|for)\s+(\w+)',
            r'how\s+(?:is|are)\s+(?:it|they)\s+implemented',
            r'implementation\s+of\s+(\w+)',
        ],
        QueryIntentType.FIND_PATTERN: [
            r'find\s+(?:code\s+)?pattern\s+(?:for|like)\s+(.+)',
            r'(?:similar|like)\s+(?:pattern|code)\s+(?:for|to)\s+(.+)',
            r'pattern[s]?\s+(?:for|like)\s+(.+)',
        ],
        QueryIntentType.UNDERSTAND_FLOW: [
            r'(?:explain|understand|trace)\s+(?:the\s+)?(?:flow|execution|logic)\s+(?:of|in)\s+(\w+)',
            r'(?:flow|execution|logic)\s+(?:of|in)\s+(\w+)',
            r'how\s+(?:does|do)\s+(\w+)\s+work',
        ],
        QueryIntentType.FIND_SIMILAR: [
            r'find\s+(?:similar|related|equivalent)\s+(?:code|function|implementation)',
            r'what\s+(?:is|are)\s+similar\s+(?:to|as)\s+(?:this|that)',
            r'similar\s+(?:code|pattern)\s+(?:to|as)\s+(.+)',
        ],
    }
    
    @staticmethod
    def analyze(query: str) -> QueryStructure:
        """Analyze query structure and extract intent."""
        query_lower = query.lower()
        structure = QueryStructure(
            original_query=query,
            intent=QueryIntentType.CUSTOM
        )
        
        # Detect intent
        for intent_type, patterns in StructureAwareAnalyzer.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    structure.intent = intent_type
                    break
            if structure.intent != QueryIntentType.CUSTOM:
                break
        
        # Separate code snippets from natural language
        structure.code_snippets = StructureAwareAnalyzer._extract_code_snippets(query)
        structure.natural_language = StructureAwareAnalyzer._extract_natural_language(query)
        
        # Extract keywords
        structure.keywords = StructureAwareAnalyzer._extract_keywords(query)
        
        # Extract constraints (file, line, type, etc.)
        structure.constraints = StructureAwareAnalyzer._extract_constraints(query)
        
        return structure
    
    @staticmethod
    def _extract_code_snippets(query: str) -> List[str]:
        """Extract code snippets from query (enclosed in backticks or code blocks)."""
        snippets = []
        
        # Match triple backticks
        triple_backtick_pattern = r'```[\w]*\n(.*?)\n```'
        matches = re.findall(triple_backtick_pattern, query, re.DOTALL)
        snippets.extend(matches)
        
        # Match single backticks
        single_backtick_pattern = r'`([^`]+)`'
        matches = re.findall(single_backtick_pattern, query)
        snippets.extend(matches)
        
        # Match indented code blocks (4+ spaces)
        lines = query.split('\n')
        code_block = []
        for line in lines:
            if line.startswith('    ') or line.startswith('\t'):
                code_block.append(line.lstrip())
            elif code_block:
                snippets.append('\n'.join(code_block))
                code_block = []
        
        if code_block:
            snippets.append('\n'.join(code_block))
        
        return snippets
    
    @staticmethod
    def _extract_natural_language(query: str) -> str:
        """Extract natural language part (remove code blocks)."""
        # Remove code blocks
        text = re.sub(r'```[\w]*\n.*?\n```', '', query, flags=re.DOTALL)
        text = re.sub(r'`[^`]+`', '', text)
        return text.strip()
    
    @staticmethod
    def _extract_keywords(query: str) -> Set[str]:
        """Extract important keywords from query."""
        keywords = set()
        
        # Intent-related keywords
        intent_keywords = {
            'find', 'search', 'locate', 'identify', 'show', 'display',
            'function', 'class', 'method', 'implementation', 'usage', 'caller',
            'pattern', 'similar', 'related', 'equivalent', 'flow', 'execution',
            'trace', 'understand', 'explain', 'code', 'logic'
        }
        
        words = re.findall(r'\b\w+\b', query.lower())
        for word in words:
            if word in intent_keywords:
                keywords.add(word)
        
        return keywords
    
    @staticmethod
    def _extract_constraints(query: str) -> Dict[str, Any]:
        """Extract constraints like file, line number, type."""
        constraints = {}
        
        # File constraint: "in file.py" or "from file.py"
        file_match = re.search(r'(?:in|from|file)\s+(?:the\s+)?file\s+["\']?([^\s"\']+)["\']?', query, re.IGNORECASE)
        if file_match:
            constraints['file'] = file_match.group(1)
        
        # Line constraint: "at line 42" or "around line 42"
        line_match = re.search(r'(?:at|around|line)\s+(\d+)', query, re.IGNORECASE)
        if line_match:
            constraints['line'] = int(line_match.group(1))
        
        # Type constraint: "type: async" or "async function"
        if re.search(r'async\s+(?:function|method)', query, re.IGNORECASE):
            constraints['type'] = 'async'
        
        if re.search(r'(?:static|class)\s+method', query, re.IGNORECASE):
            constraints['method_type'] = 'static'
        
        # Visibility constraint
        if re.search(r'(?:public|private)\s+(?:method|function)', query, re.IGNORECASE):
            constraints['visibility'] = 'public' if 'public' in query else 'private'
        
        return constraints


class SymbolAwareParser:
    """Identifies and parses symbols in queries."""
    
    @staticmethod
    def extract_symbols(query: str, knowledge_graph: Optional[Dict] = None) -> Tuple[List[Symbol], List[Symbol]]:
        """
        Extract symbols from query.
        Returns: (primary_symbols, secondary_symbols)
        """
        primary = []
        secondary = []
        
        # Extract identifiers (camelCase, snake_case, PascalCase)
        identifier_pattern = r'\b([a-zA-Z_]\w*)\b'
        matches = re.finditer(identifier_pattern, query)
        
        for match in matches:
            identifier = match.group(1)
            start = match.start()
            
            # Get surrounding context
            context_start = max(0, start - 30)
            context_end = min(len(query), start + 30)
            context = query[context_start:context_end]
            
            # Determine symbol type
            symbol_type = SymbolAwareParser._determine_symbol_type(identifier, query, start)
            
            # Calculate confidence
            confidence = SymbolAwareParser._calculate_confidence(identifier, query, context)
            
            symbol = Symbol(
                name=identifier,
                type=symbol_type,
                confidence=confidence,
                context=context
            )
            
            # Check if primary or secondary
            if confidence > 0.7:
                if symbol not in primary:
                    primary.append(symbol)
            else:
                if symbol not in secondary:
                    secondary.append(symbol)
        
        # If knowledge graph available, validate symbols and find related ones
        if knowledge_graph:
            primary = SymbolAwareParser._validate_with_kg(primary, knowledge_graph)
            secondary = SymbolAwareParser._validate_with_kg(secondary, knowledge_graph)
        
        return primary, secondary
    
    @staticmethod
    def _determine_symbol_type(identifier: str, query: str, position: int) -> SymbolType:
        """Determine the type of symbol based on context."""
        query_lower = query.lower()
        
        # Check surrounding keywords
        before_context = query_lower[max(0, position - 50):position]
        after_context = query_lower[position:min(len(query_lower), position + 50)]
        
        # Function indicators
        if re.search(r'def\s+$', before_context) or '(' in after_context[:10]:
            return SymbolType.FUNCTION
        
        # Class indicators
        if re.search(r'class\s+$', before_context) or identifier[0].isupper():
            return SymbolType.CLASS
        
        # Method indicators (after a dot)
        if before_context.strip().endswith('.'):
            return SymbolType.METHOD
        
        # Import indicators
        if re.search(r'(?:from|import)\s+', before_context):
            return SymbolType.IMPORT
        
        # Decorator indicators
        if before_context.rstrip().endswith('@'):
            return SymbolType.DECORATOR
        
        # Attribute indicators
        if before_context.endswith('.'):
            return SymbolType.ATTRIBUTE
        
        # Default to variable
        return SymbolType.VARIABLE
    
    @staticmethod
    def _calculate_confidence(identifier: str, query: str, context: str) -> float:
        """Calculate confidence that this is a meaningful symbol."""
        confidence = 0.5
        
        # Length-based heuristic: longer identifiers = higher confidence
        confidence += min(0.2, len(identifier) / 30)
        
        # CamelCase or snake_case = higher confidence
        if '_' in identifier or any(c.isupper() for c in identifier[1:]):
            confidence += 0.15
        
        # Position in query (earlier = higher confidence for function finding)
        pos_ratio = query.find(identifier) / max(len(query), 1)
        if pos_ratio < 0.3:
            confidence += 0.1
        
        # Not a common word
        common_words = {'the', 'is', 'are', 'and', 'or', 'not', 'a', 'an', 'to', 'from', 'in', 'out', 'if', 'else', 'for', 'while', 'return'}
        if identifier.lower() not in common_words:
            confidence += 0.05
        
        return min(1.0, confidence)
    
    @staticmethod
    def _validate_with_kg(symbols: List[Symbol], kg: Dict) -> List[Symbol]:
        """Validate and enrich symbols using knowledge graph."""
        validated = []
        kg_nodes = kg.get('nodes', {})
        
        for symbol in symbols:
            # Check if symbol exists in KG
            found = False
            for node_id, node_data in kg_nodes.items():
                if node_data.get('name') == symbol.name:
                    found = True
                    symbol.confidence = min(1.0, symbol.confidence + 0.2)
                    break
            
            if found or symbol.confidence > 0.5:
                validated.append(symbol)
        
        return validated


class KGAwareExpander:
    """Expands queries using knowledge graph relationships."""
    
    @staticmethod
    def expand_query(structure: QueryStructure, kg: Dict) -> Dict[str, Any]:
        """
        Expand query using knowledge graph.
        Returns expanded query context with related symbols, patterns, and files.
        """
        expansion = {
            "original_symbols": [s.name for s in structure.get_all_symbols()],
            "related_functions": set(),
            "related_classes": set(),
            "related_files": set(),
            "related_patterns": set(),
            "suggested_context": [],
            "call_chain": {},
            "inheritance_chain": {},
        }
        
        kg_nodes = kg.get('nodes', {})
        kg_edges = kg.get('edges', [])
        
        # For each symbol in query, find related nodes in KG
        for symbol in structure.get_all_symbols():
            related = KGAwareExpander._find_related_nodes(
                symbol.name, kg_nodes, kg_edges
            )
            
            for related_node in related:
                node_data = kg_nodes.get(related_node, {})
                node_type = node_data.get('type', '')
                
                if node_type == 'function':
                    expansion["related_functions"].add(node_data.get('name', ''))
                elif node_type == 'class':
                    expansion["related_classes"].add(node_data.get('name', ''))
                
                file_path = node_data.get('file', '')
                if file_path:
                    expansion["related_files"].add(file_path)
        
        # Find call chains if looking for usage or caller
        if structure.intent in [QueryIntentType.FIND_USAGE, QueryIntentType.FIND_CALLER]:
            for symbol in structure.get_all_symbols():
                call_chain = KGAwareExpander._trace_call_chain(
                    symbol.name, kg_nodes, kg_edges, structure.intent
                )
                if call_chain:
                    expansion["call_chain"][symbol.name] = call_chain
        
        # Find inheritance chains if looking for classes
        if structure.intent == QueryIntentType.FIND_CLASS:
            for symbol in structure.get_all_symbols():
                inheritance = KGAwareExpander._trace_inheritance(
                    symbol.name, kg_nodes, kg_edges
                )
                if inheritance:
                    expansion["inheritance_chain"][symbol.name] = inheritance
        
        return expansion
    
    @staticmethod
    def _find_related_nodes(
        symbol_name: str, kg_nodes: Dict, kg_edges: List
    ) -> Set[str]:
        """Find nodes related to a symbol in the knowledge graph."""
        related = set()
        
        # Find the symbol's node
        source_node = None
        for node_id, node_data in kg_nodes.items():
            if node_data.get('name') == symbol_name:
                source_node = node_id
                break
        
        if not source_node:
            return related
        
        # Find connected nodes
        for edge in kg_edges:
            if edge.get('source') == source_node:
                target = edge.get('target')
                if target:
                    related.add(target)
            elif edge.get('target') == source_node:
                source = edge.get('source')
                if source:
                    related.add(source)
        
        return related
    
    @staticmethod
    def _trace_call_chain(
        symbol_name: str, kg_nodes: Dict, kg_edges: List, 
        intent: QueryIntentType, max_depth: int = 5
    ) -> List[str]:
        """Trace call chain for a symbol."""
        chain = []
        visited = set()
        
        def _traverse(node_id: str, depth: int) -> None:
            if depth > max_depth or node_id in visited:
                return
            visited.add(node_id)
            
            node_data = kg_nodes.get(node_id, {})
            chain.append(node_data.get('name', node_id))
            
            # Direction depends on intent
            if intent == QueryIntentType.FIND_CALLER:
                # Find nodes that call this one
                for edge in kg_edges:
                    if edge.get('target') == node_id and edge.get('type') == 'calls':
                        _traverse(edge.get('source'), depth + 1)
            else:
                # Find nodes this one calls
                for edge in kg_edges:
                    if edge.get('source') == node_id and edge.get('type') == 'calls':
                        _traverse(edge.get('target'), depth + 1)
        
        # Find starting node
        for node_id, node_data in kg_nodes.items():
            if node_data.get('name') == symbol_name:
                _traverse(node_id, 0)
                break
        
        return chain
    
    @staticmethod
    def _trace_inheritance(
        class_name: str, kg_nodes: Dict, kg_edges: List, max_depth: int = 5
    ) -> Dict[str, List[str]]:
        """Trace inheritance chain for a class."""
        inheritance = {
            "bases": [],
            "derived": []
        }
        
        # Find the class node
        class_node = None
        for node_id, node_data in kg_nodes.items():
            if node_data.get('name') == class_name and node_data.get('type') == 'class':
                class_node = node_id
                break
        
        if not class_node:
            return inheritance
        
        # Find base classes (inheritance edges pointing to)
        for edge in kg_edges:
            if edge.get('source') == class_node and edge.get('type') in ['inherits', 'extends']:
                target_node = kg_nodes.get(edge.get('target'), {})
                inheritance["bases"].append(target_node.get('name', ''))
        
        # Find derived classes (inheritance edges coming from)
        for edge in kg_edges:
            if edge.get('target') == class_node and edge.get('type') in ['inherits', 'extends']:
                source_node = kg_nodes.get(edge.get('source'), {})
                inheritance["derived"].append(source_node.get('name', ''))
        
        return inheritance


class QueryUnderstanding:
    """
    Integrated query understanding system combining structure, symbol, and KG awareness.
    """
    
    def __init__(self, knowledge_graph: Optional[Dict] = None):
        """
        Initialize query understanding system.
        
        Args:
            knowledge_graph: Optional knowledge graph data for KG-aware processing
        """
        self.kg = knowledge_graph or {}
        self.structure_analyzer = StructureAwareAnalyzer()
        self.symbol_parser = SymbolAwareParser()
        self.kg_expander = KGAwareExpander()
    
    def understand(self, query: str) -> Dict[str, Any]:
        """
        Perform complete query understanding.
        
        Returns:
            Dictionary with:
            - structure: QueryStructure
            - primary_symbols: List[Symbol]
            - secondary_symbols: List[Symbol]
            - kg_expansion: Dict with related context
            - summary: Human-readable summary
        """
        # 1. Structure-aware analysis
        structure = self.structure_analyzer.analyze(query)
        
        # 2. Symbol-aware parsing
        primary_symbols, secondary_symbols = self.symbol_parser.extract_symbols(query, self.kg)
        structure.primary_symbols = primary_symbols
        structure.secondary_symbols = secondary_symbols
        
        # 3. KG-aware expansion
        kg_expansion = {}
        if self.kg:
            kg_expansion = self.kg_expander.expand_query(structure, self.kg)
        
        # Generate summary
        summary = self._generate_summary(structure, primary_symbols, kg_expansion)
        
        return {
            "structure": structure,
            "primary_symbols": primary_symbols,
            "secondary_symbols": secondary_symbols,
            "kg_expansion": kg_expansion,
            "summary": summary,
            "intent": structure.intent.value,
            "has_code": structure.has_code_snippet(),
            "constraints": structure.constraints,
        }
    
    def _generate_summary(self, structure: QueryStructure, symbols: List[Symbol], 
                        kg_expansion: Dict) -> str:
        """Generate human-readable summary of query understanding."""
        parts = []
        
        # Intent summary
        intent_text = {
            QueryIntentType.FIND_FUNCTION: "Find a function",
            QueryIntentType.FIND_CLASS: "Find a class",
            QueryIntentType.FIND_USAGE: "Find where a symbol is used",
            QueryIntentType.FIND_CALLER: "Find what calls a symbol",
            QueryIntentType.FIND_IMPLEMENTATION: "Find the implementation",
            QueryIntentType.FIND_PATTERN: "Find a code pattern",
            QueryIntentType.UNDERSTAND_FLOW: "Understand the execution flow",
            QueryIntentType.FIND_SIMILAR: "Find similar code",
            QueryIntentType.CUSTOM: "Answer a custom question",
        }
        parts.append(f"Intent: {intent_text.get(structure.intent, 'Custom query')}")
        
        # Primary symbols
        if symbols:
            symbol_names = [s.name for s in symbols]
            parts.append(f"Symbols: {', '.join(symbol_names)}")
        
        # Related context from KG
        if kg_expansion:
            if kg_expansion.get("related_functions"):
                parts.append(f"Related functions: {len(kg_expansion['related_functions'])} found")
            if kg_expansion.get("related_files"):
                parts.append(f"Related files: {len(kg_expansion['related_files'])} found")
        
        # Constraints
        if structure.constraints:
            constraint_strs = [f"{k}={v}" for k, v in structure.constraints.items()]
            parts.append(f"Constraints: {', '.join(constraint_strs)}")
        
        return " | ".join(parts)
