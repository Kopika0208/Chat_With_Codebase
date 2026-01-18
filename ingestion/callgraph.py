# callgraph.py - Call graph extraction for Python and JavaScript/TypeScript

import ast
from typing import List, Tuple


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
    Use Tree-sitter to extract function -> function calls in JS/TS.
    Returns list of (caller_name, callee_symbol).
    """
    # Try to import tree-sitter
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language
    except Exception:
        return []

    EXT_TO_TS_LANG = {
        ".js": "javascript",
        ".ts": "typescript",
    }

    lang_name = EXT_TO_TS_LANG.get(file_ext)
    if lang_name not in ("javascript", "typescript"):
        return []

    try:
        language = get_language(lang_name)
        parser = Parser()
        parser.set_language(language)
    except Exception:
        return []

    source_bytes = text.encode()
    tree = parser.parse(source_bytes)
    root = tree.root_node

    calls = []
    current_func = None

    def walk(node):
        nonlocal current_func

        # function_declaration or method_definition
        if node.type in ("function_declaration", "method_definition"):
            name_node = None
            for c in node.children:
                if c.type == "identifier":
                    name_node = c
                    break
            if name_node:
                current_func = source_bytes[name_node.start_byte:name_node.end_byte].decode(errors="ignore")

        # call_expression
        if node.type == "call_expression":
            try:
                func_node = node.child_by_field_name("function")
                if func_node:
                    callee = source_bytes[func_node.start_byte:func_node.end_byte].decode(errors="ignore")
                    if current_func and callee:
                        calls.append((current_func, callee))
            except Exception:
                pass

        for c in node.children:
            walk(c)

    walk(root)
    return calls
