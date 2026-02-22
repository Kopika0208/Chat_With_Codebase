# callgraph.py - Call graph extraction for all languages

import ast
from typing import List, Tuple, Optional
from .semantic_analyzer import TreeSitterSemanticAnalyzer, _HAS_TREE_SITTER


def extract_python_calls(text: str) -> List[Tuple[str, str]]:
    """
    Use Python AST to extract function -> function calls (within a file).
    Returns list of (caller_name, callee_symbol).
    """
    calls = []
    try:
        tree = ast.parse(text)
    except Exception:
        return calls

    current_func = None

    class CallVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            nonlocal current_func
            current_func = node.name
            self.generic_visit(node)
            current_func = None

        def visit_AsyncFunctionDef(self, node):
            nonlocal current_func
            current_func = node.name
            self.generic_visit(node)
            current_func = None

        def visit_Call(self, node):
            if current_func:
                callee = None
                if isinstance(node.func, ast.Name):
                    callee = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    callee = node.func.attr
                if callee:
                    calls.append((current_func, callee))
            self.generic_visit(node)

    CallVisitor().visit(tree)
    return calls


def extract_js_ts_calls(text: str, file_ext: str) -> List[Tuple[str, str]]:
    """
    Use Tree-sitter to extract function -> function calls in JS/TS and other languages.
    Returns list of (caller_name, callee_symbol).
    
    Supports: JavaScript, TypeScript, Java, C, C++, Go, Rust, and more.
    """
    if not _HAS_TREE_SITTER:
        return []
    
    # Map file extensions to language names
    ext_to_lang = {
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".go": "go",
        ".rs": "rust",
    }
    
    language = ext_to_lang.get(file_ext.lower())
    if not language:
        return []
    
    try:
        analyzer = TreeSitterSemanticAnalyzer("", text, language)
        return analyzer.extract_call_graph()
    except Exception:
        return []


def extract_calls_unified(text: str, file_ext: str) -> List[Tuple[str, str]]:
    """
    Unified call graph extraction for ANY language.
    
    Uses:
    - Python AST for .py files (more accurate for Python)
    - Tree-sitter semantic analyzer for all other languages (Java, C++, JavaScript, etc.)
    
    Returns list of (caller_name, callee_symbol).
    """
    if file_ext.lower() == ".py":
        return extract_python_calls(text)
    else:
        return extract_js_ts_calls(text, file_ext)
