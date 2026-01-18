# resolver.py - Symbol resolution and cross-reference analysis

from typing import Dict, List, Optional, Any, Set
from collections import defaultdict
from .symbols import Symbol, SymbolTable


class SymbolResolver:
    """Resolve symbols across multiple files and build cross-references."""
    
    def __init__(self):
        self.symbol_tables: Dict[str, SymbolTable] = {}
        self.global_symbol_index: Dict[str, List[Symbol]] = defaultdict(list)
        self.references: Dict[str, Set[str]] = defaultdict(set)  # symbol FQN -> referencing FQNs
    
    def add_symbol_table(self, file_path: str, symbol_table: SymbolTable) -> None:
        """Add a symbol table from a file to the global index."""
        self.symbol_tables[file_path] = symbol_table
        
        # Index all symbols globally by name
        for fqn, symbol in symbol_table.all_symbols.items():
            self.global_symbol_index[symbol.name].append(symbol)
    
    def resolve_symbol(self, name: str, context_file: str = None) -> Optional[Symbol]:
        """
        Resolve a symbol name in a context.
        Tries context file first, then global scope.
        """
        if context_file and context_file in self.symbol_tables:
            local_symbol = self.symbol_tables[context_file].lookup(name)
            if local_symbol:
                return local_symbol
        
        # Fallback to global index
        candidates = self.global_symbol_index.get(name, [])
        if candidates:
            return candidates[0]  # Return first match
        
        return None
    
    def resolve_attribute(self, obj_name: str, attr_name: str, context_file: str = None) -> Optional[Symbol]:
        """Resolve obj.attr in a specific context."""
        if context_file and context_file in self.symbol_tables:
            return self.symbol_tables[context_file].resolve_attribute_access(obj_name, attr_name)
        return None
    
    def build_cross_references(self) -> None:
        """Analyze all symbols and build reference relationships."""
        for file_path, st in self.symbol_tables.items():
            for fqn, symbol in st.all_symbols.items():
                # For each reference in symbol.references, add to global references
                for ref in symbol.references:
                    self.references[fqn].add(ref)
    
    def get_call_chain(self, start_symbol: str, max_depth: int = 5) -> Dict[str, List[str]]:
        """Get the complete call chain from a starting symbol."""
        chain = {}
        visited = set()
        
        def _traverse(symbol_fqn: str, depth: int) -> None:
            if depth > max_depth or symbol_fqn in visited:
                return
            visited.add(symbol_fqn)
            
            # Find symbols that call this one
            callers = [s for s, refs in self.references.items() if symbol_fqn in refs]
            chain[symbol_fqn] = callers
            
            for caller in callers:
                _traverse(caller, depth + 1)
        
        _traverse(start_symbol, 0)
        return chain
    
    def export_cross_reference_graph(self) -> Dict[str, Any]:
        """Export all cross-reference data as JSON-serializable dict."""
        return {
            "global_symbols": {
                name: [
                    {
                        "fqn": s.fully_qualified_name,
                        "file": s.file_path,
                        "line": s.line_number,
                        "kind": s.kind,
                        "is_private": s.is_private,
                    }
                    for s in symbols
                ]
                for name, symbols in self.global_symbol_index.items()
            },
            "references": {
                symbol: list(refs)
                for symbol, refs in self.references.items()
            },
            "files": list(self.symbol_tables.keys()),
        }
