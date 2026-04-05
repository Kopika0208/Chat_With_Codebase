# semantic_analyzer.py - Unified semantic analysis for all languages via Tree-sitter

import threading
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any, Callable
from .symbols import SymbolTable, TypeInfo, Symbol

try:
    from tree_sitter import Parser, Node, Language
    try:
        from tree_sitter_languages import get_language
        _HAS_TS_LANGS = True
    except Exception:
        _HAS_TS_LANGS = False
    _HAS_TREE_SITTER = True
except Exception:
    _HAS_TREE_SITTER = False
    Node = Any
    Language = Any


_THREAD_LOCAL = threading.local()


@lru_cache(maxsize=None)
def _get_cached_language(language_name: str):
    if not _HAS_TS_LANGS:
        return None
    try:
        return get_language(language_name)
    except Exception:
        return None


def _get_thread_local_parser(language_name: str):
    if not _HAS_TREE_SITTER:
        return None

    parser_cache = getattr(_THREAD_LOCAL, "parsers", None)
    if parser_cache is None:
        parser_cache = {}
        _THREAD_LOCAL.parsers = parser_cache

    parser = parser_cache.get(language_name)
    if parser is not None:
        return parser

    lang_obj = _get_cached_language(language_name)
    if lang_obj is None:
        return None

    try:
        parser = Parser()
        parser.set_language(lang_obj)
    except Exception:
        return None

    parser_cache[language_name] = parser
    return parser


class TreeSitterSemanticAnalyzer:
    """
    Language-agnostic semantic analyzer using Tree-sitter.
    Provides symbol extraction, scope tracking, and call graph linking for all languages.
    """
    
    # Language-specific node type mappings
    LANGUAGE_CONFIG = {
        "python": {
            "class_def": "class_definition",
            "func_def": ["function_definition"],
            "method_def": "function_definition",  # Python treats methods as functions in classes
            "import_stmt": ["import_statement", "import_from_statement"],
            "call_expr": "call",
            "identifier": "identifier",
            "attribute": "attribute",
        },
        "java": {
            "class_def": "class_declaration",
            "func_def": ["method_declaration"],
            "method_def": "method_declaration",
            "import_stmt": ["import_declaration"],
            "call_expr": "method_invocation",
            "identifier": "identifier",
            "attribute": "field_access",
        },
        "cpp": {
            "class_def": ["class_specifier", "struct_specifier"],
            "func_def": ["function_definition"],
            "method_def": "function_definition",
            "import_stmt": ["preproc_include"],
            "call_expr": "call_expression",
            "identifier": "identifier",
            "attribute": "field_expression",
        },
        "c": {
            "class_def": ["struct", "union"],
            "func_def": ["function_definition"],
            "method_def": "function_definition",
            "import_stmt": ["preproc_include"],
            "call_expr": "call_expression",
            "identifier": "identifier",
            "attribute": "field_expression",
        },
        "javascript": {
            "class_def": "class_declaration",
            "func_def": ["function_declaration", "arrow_function"],
            "method_def": "method_definition",
            "import_stmt": ["import_statement"],
            "call_expr": "call_expression",
            "identifier": "identifier",
            "attribute": "member_expression",
        },
        "typescript": {
            "class_def": "class_declaration",
            "func_def": ["function_declaration", "arrow_function"],
            "method_def": "method_definition",
            "import_stmt": ["import_statement"],
            "call_expr": "call_expression",
            "identifier": "identifier",
            "attribute": "member_expression",
        },
        "go": {
            "class_def": "type_declaration",  # Go doesn't have classes, uses types
            "func_def": ["function_declaration"],
            "method_def": "method_declaration",
            "import_stmt": ["import_declaration"],
            "call_expr": "call_expression",
            "identifier": "identifier",
            "attribute": "selector_expression",
        },
        "rust": {
            "class_def": ["struct_item", "impl_item"],
            "func_def": ["function_item"],
            "method_def": "function_item",
            "import_stmt": ["use_declaration"],
            "call_expr": "call_expression",
            "identifier": "identifier",
            "attribute": "field_expression",
        },
    }
    
    EXT_TO_LANG = {
        ".py": "python",
        ".java": "java",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
    }
    
    def __init__(self, file_path: str, source_code: str, language: Optional[str] = None):
        """Initialize analyzer for a file."""
        self.file_path = file_path
        self.source_code = source_code
        self.source_bytes = source_code.encode()
        self.language = language or self._detect_language(file_path)
        self.symbol_table = SymbolTable(file_path)
        self.current_function = None  # For tracking function context
        self.current_class = None  # For tracking class context
        self.parser = None
        self.tree = None
        
        # Initialize Tree-sitter if available
        if _HAS_TREE_SITTER and self.language in self.LANGUAGE_CONFIG:
            try:
                self.parser = _get_thread_local_parser(self.language)
                if self.parser is None:
                    raise RuntimeError("Parser unavailable")
                self.tree = self.parser.parse(self.source_bytes)
            except Exception:
                self.parser = None
                self.tree = None
    
    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        for ext, lang in self.EXT_TO_LANG.items():
            if file_path.lower().endswith(ext):
                return lang
        return "unknown"
    
    def extract_symbols(self) -> SymbolTable:
        """Extract symbols from source code."""
        if not self.tree or not self.parser:
            return self.symbol_table
        
        try:
            self._walk_tree(self.tree.root_node)
        except Exception as e:
            print(f"⚠️ Error extracting symbols from {self.file_path}: {e}")
        
        return self.symbol_table
    
    def extract_call_graph(self) -> List[Tuple[str, str]]:
        """Extract call graph (caller -> callee relationships)."""
        if not self.tree:
            return []
        
        calls = []
        self._extract_calls_from_node(self.tree.root_node, calls)
        return calls
    
    def _walk_tree(self, node: Node, parent_class: Optional[str] = None) -> None:
        """Recursively walk the syntax tree and extract symbols."""
        if not node:
            return
        
        config = self.LANGUAGE_CONFIG.get(self.language, {})
        
        # Handle class/struct definitions
        class_def_type = config.get("class_def", "class_declaration")
        class_def_types = class_def_type if isinstance(class_def_type, list) else [class_def_type]
        
        if node.type in class_def_types:
            self._handle_class_definition(node)
            return
        
        # Handle function/method definitions
        func_def_types = config.get("func_def", [])
        if not isinstance(func_def_types, list):
            func_def_types = [func_def_types]
        method_def_type = config.get("method_def", "method_definition")
        all_func_types = func_def_types + [method_def_type]
        
        if node.type in all_func_types:
            # Determine if this is a method (inside a class)
            is_method = parent_class is not None
            self._handle_function_definition(node, is_method, parent_class)
            return
        
        # Handle import statements
        import_types = config.get("import_stmt", [])
        if not isinstance(import_types, list):
            import_types = [import_types]
        
        if node.type in import_types:
            self._handle_import(node)
        
        # Handle variable/field declarations
        if self.language == "java" and node.type == "field_declaration":
            self._handle_field_declaration(node)
        elif self.language in ("cpp", "c") and node.type == "declaration":
            self._handle_declaration(node)
        elif self.language in ("javascript", "typescript") and node.type == "variable_declarator":
            self._handle_variable_declarator(node)
        
        # Recurse into children
        for child in node.children:
            # Track parent class context
            child_parent_class = parent_class
            if node.type in class_def_types:
                child_parent_class = self._get_node_name(node)
            
            self._walk_tree(child, child_parent_class)
    
    def _handle_class_definition(self, node: Node) -> None:
        """Handle class/struct/interface definitions."""
        name = self._get_node_name(node)
        if not name:
            return
        
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        docstring = self._extract_docstring(node)
        
        # Add class symbol
        self.symbol_table.add_symbol(
            name=name,
            kind="class",
            line_number=start_line,
            end_line=end_line,
            docstring=docstring,
            is_private=name.startswith("_")
        )
        
        # Extract base classes if available
        mro = self._extract_base_classes(node)
        
        # Push class scope for members
        self.symbol_table.push_scope(name, "class", mro=mro)
        
        # Process class members
        for child in node.children:
            self._walk_tree(child, name)
        
        self.symbol_table.pop_scope()
    
    def _handle_function_definition(self, node: Node, is_method: bool = False, parent_class: Optional[str] = None) -> None:
        """Handle function/method definitions."""
        name = self._get_node_name(node)
        if not name:
            return
        
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        docstring = self._extract_docstring(node)
        
        # Extract parameters
        params = self._extract_parameters(node)
        
        # Extract decorators/attributes
        decorators = self._extract_decorators(node)
        is_static = any("static" in str(d).lower() for d in decorators)
        
        scope_type = "method" if is_method else "function"
        
        # Add function symbol
        symbol = self.symbol_table.add_symbol(
            name=name,
            kind=scope_type,
            line_number=start_line,
            end_line=end_line,
            docstring=docstring,
            is_static=is_static,
            is_private=name.startswith("_"),
            parent_symbol=parent_class
        )
        
        symbol.definitions["params"] = params
        symbol.definitions["decorators"] = decorators
        
        # Push function scope
        self.symbol_table.push_scope(name, scope_type)
        
        # Process function body for nested definitions
        for child in node.children:
            self._walk_tree(child, parent_class)
        
        self.symbol_table.pop_scope()
    
    def _handle_import(self, node: Node) -> None:
        """Handle import statements."""
        try:
            # Extract imported names and module
            if self.language == "python":
                self._handle_python_import(node)
            elif self.language == "java":
                self._handle_java_import(node)
            elif self.language in ("javascript", "typescript"):
                self._handle_js_import(node)
            elif self.language in ("cpp", "c"):
                self._handle_cpp_include(node)
            elif self.language == "go":
                self._handle_go_import(node)
            elif self.language == "rust":
                self._handle_rust_import(node)
        except Exception:
            pass
    
    def _handle_python_import(self, node: Node) -> None:
        """Handle Python import statements."""
        line = node.start_point[0] + 1
        source_range = self.source_code[node.start_byte:node.end_byte]
        
        if "from" in source_range:
            # from X import Y
            parts = source_range.split("import")
            if len(parts) == 2:
                module = parts[0].replace("from", "").strip()
                imports = [x.strip() for x in parts[1].split(",")]
                for imp in imports:
                    clean_imp = imp.split("as")[-1].strip()
                    if clean_imp and clean_imp != "*":
                        self.symbol_table.add_symbol(
                            name=clean_imp,
                            kind="import",
                            line_number=line,
                            end_line=line,
                            docstring=f"from {module} import {imp}"
                        )
                        self.symbol_table.add_import(clean_imp, f"{module}.{clean_imp}")
        else:
            # import X [as Y]
            parts = source_range.replace("import", "").split(",")
            for part in parts:
                if "as" in part:
                    _, alias = part.split("as")
                    name = alias.strip()
                else:
                    name = part.strip()
                
                if name:
                    self.symbol_table.add_symbol(
                        name=name,
                        kind="import",
                        line_number=line,
                        end_line=line,
                        docstring=f"import {name}"
                    )
                    self.symbol_table.add_import(name, name)
    
    def _handle_java_import(self, node: Node) -> None:
        """Handle Java import statements."""
        line = node.start_point[0] + 1
        source_text = self.source_code[node.start_byte:node.end_byte].strip()
        
        # Extract the imported class/package
        match = source_text.replace("import", "").replace(";", "").strip()
        
        # Get the simple name (last part after dot)
        if "." in match:
            simple_name = match.split(".")[-1]
        else:
            simple_name = match
        
        self.symbol_table.add_symbol(
            name=simple_name,
            kind="import",
            line_number=line,
            end_line=line,
            docstring=f"import {match}"
        )
        self.symbol_table.add_import(simple_name, match)
    
    def _handle_js_import(self, node: Node) -> None:
        """Handle JavaScript/TypeScript import statements."""
        line = node.start_point[0] + 1
        source_text = self.source_code[node.start_byte:node.end_byte]
        
        # Extract imported names (basic parsing)
        if "from" in source_text:
            parts = source_text.split("from")
            if len(parts) >= 2:
                imports_part = parts[0].replace("import", "").strip()
                module = parts[1].replace(";", "").strip().strip("'\"")
                
                # Parse imports (simple names only, not destructuring)
                for name in imports_part.split(","):
                    clean_name = name.strip().split("as")[-1].strip()
                    if clean_name and clean_name != "*":
                        self.symbol_table.add_symbol(
                            name=clean_name,
                            kind="import",
                            line_number=line,
                            end_line=line,
                            docstring=f"import from {module}"
                        )
                        self.symbol_table.add_import(clean_name, module)
    
    def _handle_cpp_include(self, node: Node) -> None:
        """Handle C/C++ include statements."""
        line = node.start_point[0] + 1
        source_text = self.source_code[node.start_byte:node.end_byte]
        
        # Extract header name
        if "<" in source_text:
            header = source_text.split("<")[1].split(">")[0].strip()
        elif '"' in source_text:
            header = source_text.split('"')[1].strip()
        else:
            return
        
        self.symbol_table.add_symbol(
            name=header,
            kind="import",
            line_number=line,
            end_line=line,
            docstring=f"#include {header}"
        )
    
    def _handle_go_import(self, node: Node) -> None:
        """Handle Go import statements."""
        line = node.start_point[0] + 1
        source_text = self.source_code[node.start_byte:node.end_byte]
        
        # Extract package path
        if '"' in source_text:
            package = source_text.split('"')[1].strip()
            simple_name = package.split("/")[-1]
            
            self.symbol_table.add_symbol(
                name=simple_name,
                kind="import",
                line_number=line,
                end_line=line,
                docstring=f"import {package}"
            )
            self.symbol_table.add_import(simple_name, package)
    
    def _handle_rust_import(self, node: Node) -> None:
        """Handle Rust use statements."""
        line = node.start_point[0] + 1
        source_text = self.source_code[node.start_byte:node.end_byte].replace("use", "").replace(";", "").strip()
        
        # Extract the last part as the name
        if "::" in source_text:
            parts = source_text.split("::")
            name = parts[-1].split("as")[-1].strip()
        else:
            name = source_text.split("as")[-1].strip()
        
        if name:
            self.symbol_table.add_symbol(
                name=name,
                kind="import",
                line_number=line,
                end_line=line,
                docstring=f"use {source_text}"
            )
            self.symbol_table.add_import(name, source_text)
    
    def _handle_field_declaration(self, node: Node) -> None:
        """Handle Java field declarations."""
        for child in node.children:
            if child.type == "variable_declarator":
                name = self._get_node_name(child)
                if name:
                    line = child.start_point[0] + 1
                    self.symbol_table.add_symbol(
                        name=name,
                        kind="variable",
                        line_number=line,
                        end_line=line,
                        is_private=self._is_private_in_java(node)
                    )
    
    def _handle_declaration(self, node: Node) -> None:
        """Handle C/C++ variable declarations."""
        for child in node.children:
            if child.type == "declarator":
                name = self._get_node_name(child)
                if name:
                    line = child.start_point[0] + 1
                    self.symbol_table.add_symbol(
                        name=name,
                        kind="variable",
                        line_number=line,
                        end_line=line
                    )
    
    def _handle_variable_declarator(self, node: Node) -> None:
        """Handle JavaScript/TypeScript variable declarations."""
        name = self._get_node_name(node)
        if name:
            line = node.start_point[0] + 1
            self.symbol_table.add_symbol(
                name=name,
                kind="variable",
                line_number=line,
                end_line=line,
                is_private=name.startswith("_")
            )
    
    def _get_node_name(self, node: Node) -> Optional[str]:
        """Extract the name from a node."""
        # Try to find identifier child
        for child in node.children:
            if child.type == "identifier":
                return self.source_code[child.start_byte:child.end_byte].strip()
        
        # Fallback: check specific node types
        if node.type == "identifier":
            return self.source_code[node.start_byte:node.end_byte].strip()
        
        # For variable_declarator in JS/TS, the name is the first child
        if node.type == "variable_declarator":
            if node.children:
                return self.source_code[node.children[0].start_byte:node.children[0].end_byte].strip()
        
        return None
    
    def _extract_docstring(self, node: Node) -> Optional[str]:
        """Extract docstring from node (comments above definition)."""
        # This is a simplified approach - checks for comment nodes before the definition
        prev_node = None
        if node.start_point[0] > 0:
            # Look for comment on the line before
            line_idx = node.start_point[0] - 1
            line_start = sum(len(l) + 1 for l in self.source_code.splitlines()[:line_idx])
            line_end = line_start + len(self.source_code.splitlines()[line_idx])
            text = self.source_code[line_start:line_end].strip()
            
            if text.startswith("//") or text.startswith("#"):
                return text.lstrip("#/").strip()
        
        return None
    
    def _extract_base_classes(self, node: Node) -> List[str]:
        """Extract base classes from class definition."""
        bases = []
        try:
            if self.language == "java":
                # Look for extends/implements
                source_text = self.source_code[node.start_byte:node.end_byte]
                if "extends" in source_text:
                    extends_part = source_text.split("extends")[1].split("{")[0]
                    bases.append(extends_part.strip())
                if "implements" in source_text:
                    implements_part = source_text.split("implements")[1].split("{")[0]
                    for base in implements_part.split(","):
                        bases.append(base.strip())
            elif self.language in ("cpp", "c"):
                # Look for : followed by base classes
                source_text = self.source_code[node.start_byte:node.end_byte]
                if ":" in source_text:
                    bases_part = source_text.split(":")[1].split("{")[0]
                    for base in bases_part.split(","):
                        base_name = base.replace("public", "").replace("private", "").replace("protected", "").strip()
                        if base_name:
                            bases.append(base_name)
        except Exception:
            pass
        
        return bases
    
    def _extract_parameters(self, node: Node) -> List[Dict[str, str]]:
        """Extract function/method parameters."""
        params = []
        try:
            # Find parameters node (usually called "parameters")
            for child in node.children:
                if "parameter" in child.type or child.type in ("formal_parameters", "parameters"):
                    for param_child in child.children:
                        if param_child.type == "identifier" or "parameter" in param_child.type:
                            param_name = self._get_node_name(param_child)
                            if param_name:
                                params.append({"name": param_name})
        except Exception:
            pass
        
        return params
    
    def _extract_decorators(self, node: Node) -> List[str]:
        """Extract decorators/annotations."""
        decorators = []
        try:
            source_text = self.source_code[node.start_byte:node.end_byte]
            
            if self.language == "python":
                # Look for @decorator pattern
                lines = source_text.split("\n")
                for line in lines:
                    if line.strip().startswith("@"):
                        decorators.append(line.strip())
            elif self.language == "java":
                # Look for @Annotation pattern
                lines = source_text.split("\n")
                for line in lines:
                    if line.strip().startswith("@"):
                        decorators.append(line.strip())
        except Exception:
            pass
        
        return decorators
    
    def _is_private_in_java(self, node: Node) -> bool:
        """Check if a Java field is private."""
        source_text = self.source_code[node.start_byte:node.end_byte]
        return "private" in source_text.lower()
    
    def _extract_calls_from_node(self, node: Node, calls: List[Tuple[str, str]]) -> None:
        """Recursively extract function calls from tree."""
        if not node:
            return
        
        config = self.LANGUAGE_CONFIG.get(self.language, {})
        call_expr_type = config.get("call_expr", "call_expression")
        
        # Track current function context
        func_def_types = config.get("func_def", [])
        if not isinstance(func_def_types, list):
            func_def_types = [func_def_types]
        
        if node.type in func_def_types or node.type == config.get("method_def", "method_definition"):
            caller_name = self._get_node_name(node)
            if caller_name:
                old_func = self.current_function
                self.current_function = caller_name
                
                for child in node.children:
                    self._extract_calls_from_node(child, calls)
                
                self.current_function = old_func
                return
        
        # Detect function calls
        if node.type == call_expr_type and self.current_function:
            try:
                # Extract callee name
                callee = self._extract_callee_name(node)
                if callee:
                    calls.append((self.current_function, callee))
            except Exception:
                pass
        
        # Recurse
        for child in node.children:
            self._extract_calls_from_node(child, calls)
    
    def _extract_callee_name(self, node: Node) -> Optional[str]:
        """Extract function name being called."""
        try:
            # For most languages, the first identifier or the expression before ()
            if self.language in ("javascript", "typescript"):
                # call_expression structure: function ( arguments )
                if node.children and node.children[0].type == "member_expression":
                    # obj.method() case
                    for child in node.children[0].children:
                        if child.type == "property_identifier":
                            return self.source_code[child.start_byte:child.end_byte].strip()
                    # Fallback to last identifier
                    for child in reversed(node.children[0].children):
                        if child.type == "identifier":
                            return self.source_code[child.start_byte:child.end_byte].strip()
                elif node.children and node.children[0].type == "identifier":
                    return self.source_code[node.children[0].start_byte:node.children[0].end_byte].strip()
            
            elif self.language == "python":
                # call structure: func_name ( args )
                for child in node.children:
                    if child.type == "identifier":
                        return self.source_code[child.start_byte:child.end_byte].strip()
                    elif child.type == "attribute":
                        # method.call() case
                        for attr_child in child.children:
                            if attr_child.type == "identifier":
                                return self.source_code[attr_child.start_byte:attr_child.end_byte].strip()
            
            elif self.language == "java":
                # method_invocation structure
                for child in node.children:
                    if child.type == "identifier":
                        return self.source_code[child.start_byte:child.end_byte].strip()
            
            elif self.language in ("cpp", "c"):
                # call_expression
                for child in node.children:
                    if child.type == "identifier":
                        return self.source_code[child.start_byte:child.end_byte].strip()
            
            elif self.language == "go":
                # call_expression
                for child in node.children:
                    if child.type == "identifier":
                        return self.source_code[child.start_byte:child.end_byte].strip()
            
            elif self.language == "rust":
                # call_expression
                for child in node.children:
                    if child.type == "identifier":
                        return self.source_code[child.start_byte:child.end_byte].strip()
        
        except Exception:
            pass
        
        return None


def extract_symbols_and_calls(file_path: str, source_code: str, language: Optional[str] = None) -> Tuple[SymbolTable, List[Tuple[str, str]]]:
    """
    Unified interface to extract symbols and call graph for any supported language.
    
    Args:
        file_path: Path to the source file
        source_code: Content of the source file
        language: Optional language hint (auto-detected if not provided)
    
    Returns:
        Tuple of (SymbolTable, call_graph_list)
    """
    analyzer = TreeSitterSemanticAnalyzer(file_path, source_code, language)
    symbols = analyzer.extract_symbols()
    calls = analyzer.extract_call_graph()
    return symbols, calls
