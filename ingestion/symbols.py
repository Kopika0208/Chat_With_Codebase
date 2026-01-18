# symbols.py - Symbol table and Python symbol extraction

import ast
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class TypeInfo:
    """Represents type information for a symbol."""
    name: str
    module: Optional[str] = None
    is_builtin: bool = False
    base_types: List[str] = field(default_factory=list)  # for MRO
    
    def __str__(self):
        if self.module:
            return f"{self.module}.{self.name}"
        return self.name


@dataclass
class Symbol:
    """Represents a symbol (variable, function, class, etc) in the codebase."""
    name: str
    kind: str  # "variable", "function", "method", "class", "import", "attribute"
    scope_id: str  # globally unique scope identifier
    line_number: int
    end_line: int
    file_path: str
    type_hint: Optional[TypeInfo] = None
    is_static: bool = False  # for class members
    is_private: bool = False  # leading underscore
    docstring: Optional[str] = None
    parent_symbol: Optional[str] = None  # FQN of parent (class/function)
    references: List[str] = field(default_factory=list)  # FQNs that reference this
    definitions: Dict[str, Any] = field(default_factory=dict)  # extra metadata
    
    @property
    def fully_qualified_name(self) -> str:
        """Returns FQN: file_path:scope:name"""
        return f"{self.file_path}:{self.scope_id}:{self.name}"
    
    def __hash__(self):
        return hash(self.fully_qualified_name)
    
    def __eq__(self, other):
        if isinstance(other, Symbol):
            return self.fully_qualified_name == other.fully_qualified_name
        return False


@dataclass
class Scope:
    """Represents a lexical scope (global, class, function/method)."""
    scope_id: str  # "file:global", "file:ClassName", "file:func_name:nested_func"
    scope_type: str  # "global", "class", "function", "method"
    parent_scope_id: Optional[str] = None
    file_path: str = ""
    class_name: Optional[str] = None
    symbols: Dict[str, Symbol] = field(default_factory=dict)  # name -> Symbol
    imports: Dict[str, str] = field(default_factory=dict)  # local_name -> full_module
    local_types: Dict[str, TypeInfo] = field(default_factory=dict)  # local type definitions
    mro: List[str] = field(default_factory=list)  # Method Resolution Order (for classes)
    
    def add_symbol(self, symbol: Symbol) -> None:
        """Add a symbol to this scope."""
        self.symbols[symbol.name] = symbol
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """Lookup a symbol in this scope (no parent traversal)."""
        return self.symbols.get(name)
    
    def __str__(self):
        return f"Scope({self.scope_id}, type={self.scope_type}, symbols={len(self.symbols)})"


class SymbolTable:
    """Complete symbol table for a codebase with scope tracking and resolution."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.scopes: Dict[str, Scope] = {}
        self.all_symbols: Dict[str, Symbol] = {}  # FQN -> Symbol
        self.current_scope_stack: List[str] = []  # stack of scope_ids
        self.imports: Dict[str, str] = {}  # module_alias -> full_module_path
        
        # Initialize global scope
        global_scope_id = f"{file_path}:global"
        self.scopes[global_scope_id] = Scope(
            scope_id=global_scope_id,
            scope_type="global",
            file_path=file_path
        )
        self.current_scope_stack.append(global_scope_id)
    
    @property
    def current_scope_id(self) -> str:
        """Get the current scope ID."""
        return self.current_scope_stack[-1] if self.current_scope_stack else f"{self.file_path}:global"
    
    @property
    def current_scope(self) -> Scope:
        """Get the current scope object."""
        return self.scopes.get(self.current_scope_id) or self.scopes[f"{self.file_path}:global"]
    
    def push_scope(self, scope_name: str, scope_type: str, mro: List[str] = None) -> str:
        """Enter a new scope (class or function)."""
        parent_scope_id = self.current_scope_id
        scope_id = f"{parent_scope_id}:{scope_name}"
        
        if scope_id not in self.scopes:
            scope = Scope(
                scope_id=scope_id,
                scope_type=scope_type,
                parent_scope_id=parent_scope_id,
                file_path=self.file_path,
                class_name=scope_name if scope_type == "class" else None,
                mro=mro or []
            )
            self.scopes[scope_id] = scope
        
        self.current_scope_stack.append(scope_id)
        return scope_id
    
    def pop_scope(self) -> Optional[str]:
        """Exit the current scope."""
        if len(self.current_scope_stack) > 1:
            return self.current_scope_stack.pop()
        return None
    
    def add_symbol(self, name: str, kind: str, line_number: int, end_line: int,
                   type_hint: Optional[TypeInfo] = None, is_static: bool = False,
                   is_private: bool = False, docstring: Optional[str] = None,
                   parent_symbol: Optional[str] = None) -> Symbol:
        """Add a symbol to the current scope."""
        symbol = Symbol(
            name=name,
            kind=kind,
            scope_id=self.current_scope_id,
            line_number=line_number,
            end_line=end_line,
            file_path=self.file_path,
            type_hint=type_hint,
            is_static=is_static,
            is_private=is_private,
            docstring=docstring,
            parent_symbol=parent_symbol
        )
        
        self.current_scope.add_symbol(symbol)
        self.all_symbols[symbol.fully_qualified_name] = symbol
        return symbol
    
    def add_import(self, local_name: str, module_path: str) -> None:
        """Track an import in current scope."""
        self.imports[local_name] = module_path
        self.current_scope.imports[local_name] = module_path
    
    def resolve_attribute_access(self, obj_name: str, attr_name: str) -> Optional[Symbol]:
        """
        Resolve attribute access (e.g., obj.method or ClassName.field).
        Returns the Symbol if found, None otherwise.
        """
        # First try to find the object in current scope chain
        obj_symbol = self.lookup(obj_name)
        if not obj_symbol or not obj_symbol.type_hint:
            return None
        
        obj_class_name = obj_symbol.type_hint.name
        
        # Look for the attribute in the class scope
        for scope_id, scope in self.scopes.items():
            if obj_class_name in scope_id:
                attr_symbol = scope.lookup(attr_name)
                if attr_symbol:
                    return attr_symbol
        
        return None
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """
        Lookup a symbol by traversing the scope chain from current to global.
        """
        scope_id = self.current_scope_id
        while scope_id:
            scope = self.scopes.get(scope_id)
            if scope:
                symbol = scope.lookup(name)
                if symbol:
                    return symbol
            
            # Move to parent scope
            scope_obj = scope if scope else self.scopes.get(f"{self.file_path}:global")
            scope_id = scope_obj.parent_scope_id if scope_obj else None
        
        return None
    
    def get_class_mro(self, class_name: str) -> List[str]:
        """Get the Method Resolution Order (MRO) for a class."""
        for scope in self.scopes.values():
            if scope.scope_type == "class" and scope.class_name == class_name:
                return scope.mro
        return []
    
    def get_symbols_by_kind(self, kind: str) -> List[Symbol]:
        """Get all symbols of a specific kind (e.g., all functions)."""
        return [s for s in self.all_symbols.values() if s.kind == kind]
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export symbol table to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "symbols": {
                fqn: {
                    "name": s.name,
                    "kind": s.kind,
                    "scope_id": s.scope_id,
                    "line": s.line_number,
                    "end_line": s.end_line,
                    "is_static": s.is_static,
                    "is_private": s.is_private,
                    "type_hint": str(s.type_hint) if s.type_hint else None,
                    "parent_symbol": s.parent_symbol,
                    "docstring": s.docstring,
                }
                for fqn, s in self.all_symbols.items()
            },
            "scopes": {
                scope_id: {
                    "scope_type": scope.scope_type,
                    "parent_scope_id": scope.parent_scope_id,
                    "class_name": scope.class_name,
                    "mro": scope.mro,
                    "imports": scope.imports,
                    "symbol_count": len(scope.symbols),
                }
                for scope_id, scope in self.scopes.items()
            },
        }


class PythonSymbolExtractor(ast.NodeVisitor):
    """Extract symbols from Python source using AST."""
    
    def __init__(self, symbol_table: SymbolTable, source_code: str):
        self.symbol_table = symbol_table
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
    
    def visit_Import(self, node: ast.Import) -> None:
        """Handle: import module [as alias]"""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.symbol_table.add_symbol(
                name=name,
                kind="import",
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=f"import {alias.name}"
            )
            self.symbol_table.add_import(name, alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle: from module import name [as alias]"""
        module = node.module or ""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.symbol_table.add_symbol(
                name=name,
                kind="import",
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=f"from {module} import {alias.name}"
            )
            self.symbol_table.add_import(name, f"{module}.{alias.name}")
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Handle class definitions and extract MRO."""
        # Add class symbol
        self.symbol_table.add_symbol(
            name=node.name,
            kind="class",
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            is_private=node.name.startswith("_")
        )
        
        # Extract base classes for MRO
        mro = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                mro.append(base.id)
            elif isinstance(base, ast.Attribute):
                mro.append(ast.unparse(base) if hasattr(ast, "unparse") else str(base))
        
        # Push class scope
        self.symbol_table.push_scope(node.name, "class", mro=mro)
        self.generic_visit(node)
        self.symbol_table.pop_scope()
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handle function and method definitions."""
        self._handle_function_or_method(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Handle async function definitions."""
        self._handle_function_or_method(node, is_async=True)
    
    def _handle_function_or_method(self, node, is_async: bool = False) -> None:
        """Common handler for function/method definitions."""
        parent_scope_id = self.symbol_table.current_scope_id
        scope_type = "method" if ":" in parent_scope_id and parent_scope_id.split(":")[-2] != "global" else "function"
        
        decorators = [ast.unparse(d) if hasattr(ast, "unparse") else ast.dump(d) for d in node.decorator_list]
        is_static = any("staticmethod" in str(d) for d in decorators)
        
        params = []
        for arg in node.args.args:
            param_info = {
                "name": arg.arg,
                "annotation": ast.unparse(arg.annotation) if arg.annotation and hasattr(ast, "unparse") else None
            }
            params.append(param_info)
        
        docstring = ast.get_docstring(node)
        symbol = self.symbol_table.add_symbol(
            name=node.name,
            kind=scope_type,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            is_static=is_static,
            is_private=node.name.startswith("_"),
            docstring=docstring
        )
        
        symbol.definitions["params"] = params
        symbol.definitions["decorators"] = decorators
        symbol.definitions["is_async"] = is_async
        
        self.symbol_table.push_scope(node.name, scope_type)
        self.generic_visit(node)
        self.symbol_table.pop_scope()
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle variable assignments."""
        for target in node.targets:
            var_name = None
            type_hint = None
            
            if isinstance(target, ast.Name):
                var_name = target.id
            elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self.symbol_table.add_symbol(
                            name=elt.id,
                            kind="variable",
                            line_number=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            is_private=elt.id.startswith("_")
                        )
            
            if var_name:
                inferred_type = self._infer_type(node.value)
                self.symbol_table.add_symbol(
                    name=var_name,
                    kind="variable",
                    line_number=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    type_hint=inferred_type,
                    is_private=var_name.startswith("_")
                )
        
        self.generic_visit(node)
    
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Handle annotated assignments (var: Type = value)."""
        var_name = None
        type_hint = None
        
        if isinstance(node.target, ast.Name):
            var_name = node.target.id
            type_hint = self._extract_type_hint(node.annotation)
        
        if var_name:
            self.symbol_table.add_symbol(
                name=var_name,
                kind="variable",
                line_number=node.lineno,
                end_line=node.end_lineno or node.lineno,
                type_hint=type_hint,
                is_private=var_name.startswith("_")
            )
        
        self.generic_visit(node)
    
    def _extract_type_hint(self, annotation: ast.expr) -> Optional[TypeInfo]:
        """Extract type information from annotation."""
        if isinstance(annotation, ast.Name):
            return TypeInfo(name=annotation.id)
        elif isinstance(annotation, ast.Attribute):
            parts = []
            node = annotation
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return TypeInfo(name=".".join(reversed(parts)))
        elif hasattr(ast, "unparse"):
            return TypeInfo(name=ast.unparse(annotation))
        else:
            return TypeInfo(name=ast.dump(annotation))
    
    def _infer_type(self, value: ast.expr) -> Optional[TypeInfo]:
        """Infer type from value expression."""
        if isinstance(value, ast.Constant):
            if isinstance(value.value, int):
                return TypeInfo(name="int", is_builtin=True)
            elif isinstance(value.value, str):
                return TypeInfo(name="str", is_builtin=True)
            elif isinstance(value.value, bool):
                return TypeInfo(name="bool", is_builtin=True)
            elif isinstance(value.value, float):
                return TypeInfo(name="float", is_builtin=True)
        elif isinstance(value, ast.List):
            return TypeInfo(name="list", is_builtin=True)
        elif isinstance(value, ast.Dict):
            return TypeInfo(name="dict", is_builtin=True)
        elif isinstance(value, ast.Tuple):
            return TypeInfo(name="tuple", is_builtin=True)
        elif isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return TypeInfo(name=value.func.id)
        return None


def extract_python_symbols(file_path: str, source_code: str) -> SymbolTable:
    """
    Extract all symbols from Python source code using AST.
    Returns a populated SymbolTable.
    """
    symbol_table = SymbolTable(file_path)
    
    try:
        tree = ast.parse(source_code)
        extractor = PythonSymbolExtractor(symbol_table, source_code)
        extractor.visit(tree)
    except Exception as e:
        print(f"⚠️ Error extracting symbols from {file_path}: {e}")
    
    return symbol_table
