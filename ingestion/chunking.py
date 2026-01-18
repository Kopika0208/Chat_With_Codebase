# chunking.py - Code chunking with multiple parsers

import ast
import re
from typing import List, Dict, Optional, Any

# Tree-sitter imports (optional)
try:
    from tree_sitter import Parser
    try:
        from tree_sitter_languages import get_language
        _HAS_TS_LANGS = True
    except Exception:
        _HAS_TS_LANGS = False
    _HAS_TREE_SITTER = True
except Exception:
    _HAS_TREE_SITTER = False


# ===============================
# 🧩 FALLBACK REGEX SPLITTER
# ===============================
def simple_function_split(code: str, language: str = "unknown") -> list:
    """
    Very simple heuristic splitter when tree-sitter/AST unavailable.
    Returns list of dicts with start_line, end_line, text, node_type, name, parser_used.
    """
    lines = code.splitlines()
    n = len(lines)
    boundaries = [0]
    for i, ln in enumerate(lines):
        s = ln.strip()
        # Python
        if s.startswith("def ") or s.startswith("class "):
            boundaries.append(i)
        # JS/TS heuristics
        if re.match(r'^(export\s+)?function\s+\w+\s*\(', s) or re.match(r'^\w+\s*:\s*function\s*\(', s):
            boundaries.append(i)
        # arrow functions in JS
        if re.match(r'^\w+\s*=\s*\(.*\)\s*=>', s):
            boundaries.append(i)
    boundaries = sorted(set(boundaries))
    chunks = []
    for i, b in enumerate(boundaries):
        start = b
        end = boundaries[i + 1] if i + 1 < len(boundaries) else n
        text = "\n".join(lines[start:end]).strip()
        if text:
            # try to derive a simple name for display
            name = None
            first = lines[start].strip() if start < n else ""
            m = re.match(r'(def|class|function)\s+([A-Za-z0-9_]+)', first)
            if m:
                name = m.group(2)
            chunks.append({
                "start_line": start + 1,
                "end_line": end,
                "text": text,
                "node_type": "chunk",
                "name": name,
                "language": language,
                "parser_used": "regex_fallback",
            })
    if len(chunks) == 1 and n > 400:
        chunk_size = 200
        overlap = 50
        chunks = []
        for s in range(0, n, chunk_size - overlap):
            e = min(n, s + chunk_size)
            chunks.append({
                "start_line": s + 1,
                "end_line": e,
                "text": "\n".join(lines[s:e]),
                "node_type": "chunk",
                "name": None,
                "language": language,
                "parser_used": "regex_fallback",
            })
    return chunks


# ===============================
# ⚙️ TREE-SITTER MAPPINGS
# ===============================
EXT_TO_TS_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".rs": "rust",
    ".go": "go",
}

TS_NODE_TYPES = {
    "python": ["function_definition", "class_definition"],
    "javascript": ["function_declaration", "method_definition", "class_declaration"],
    "typescript": ["function_declaration", "method_definition", "class_declaration"],
    "java": ["method_declaration", "class_declaration"],
    "c": ["function_definition"],
    "cpp": ["function_definition", "class_specifier"],
    "rust": ["function_item", "impl_item", "struct_item", "enum_item"],
    "go": ["function_declaration", "method_declaration", "type_declaration"],
}


def _get_node_text(source_bytes: bytes, node):
    return source_bytes[node.start_byte:node.end_byte].decode(errors="ignore")


# ===============================
# 🧠 TREE-SITTER CHUNKING
# ===============================
def code_chunks_with_treesitter(text: str, file_ext: str):
    """
    Use tree-sitter to extract function/class/method level chunks.
    Returns list of dicts with rich metadata when possible.
    """
    if not _HAS_TREE_SITTER:
        return None

    lang_name = EXT_TO_TS_LANG.get(file_ext)
    if not lang_name:
        return None

    language = None
    if _HAS_TS_LANGS:
        try:
            language = get_language(lang_name)
        except Exception:
            language = None

    if language is None:
        return None

    try:
        parser = Parser()
        parser.set_language(language)
    except Exception:
        return None

    source_bytes = text.encode()
    tree = parser.parse(source_bytes)
    root = tree.root_node
    node_types_of_interest = TS_NODE_TYPES.get(lang_name, [])
    chunks = []

    def extract_name(node):
        for child in node.children:
            if child.type in ("identifier", "name", "attribute", "function_name"):
                try:
                    return _get_node_text(source_bytes, child).strip()
                except Exception:
                    return None
        return None

    # extract imports (best-effort) for context
    imports = []
    try:
        for m in re.finditer(r'^\s*(?:from\s+[\w\.]+\s+import|import\s+[\w\.]+)', text, flags=re.MULTILINE):
            imports.append(m.group(0).strip())
    except Exception:
        imports = []

    def walk(node, parent_stack=None):
        if parent_stack is None:
            parent_stack = []
        # check interest
        if node.type in node_types_of_interest:
            try:
                chunk_text = _get_node_text(source_bytes, node)
            except Exception:
                chunk_text = ""
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            name = extract_name(node)
            parent_class = None
            # infer parent class if any
            for p in reversed(parent_stack):
                if p.type == "class_definition" or p.type == "class_declaration":
                    parent_class = extract_name(p)
                    break
            # try to collect parameters and decorators if available in source text via regex (best-effort)
            params = None
            decorators = []
            try:
                first_line = chunk_text.splitlines()[0]
                sig_match = re.search(r'\((.*?)\)', first_line)
                if sig_match:
                    params = [p.strip() for p in sig_match.group(1).split(",") if p.strip()]
                src_lines = text.splitlines()
                for idx in range(max(0, start_line - 6), start_line - 1):
                    ln = src_lines[idx].strip()
                    if ln.startswith("@") or ln.startswith("# decorator"):
                        decorators.append(ln)
            except Exception:
                params = params or None
                decorators = decorators or []
            chunks.append({
                "start_line": start_line,
                "end_line": end_line,
                "text": chunk_text,
                "node_type": node.type,
                "name": name,
                "language": lang_name,
                "params": params,
                "decorators": decorators,
                "imports": imports,
                "parent_class": parent_class,
                "parser_used": "tree_sitter",
            })
        # recurse
        for c in node.children:
            walk(c, parent_stack + [node])

    walk(root, [])
    if not chunks:
        lines = text.splitlines()
        return [{
            "start_line": 1,
            "end_line": len(lines),
            "text": text,
            "node_type": "file",
            "name": None,
            "language": lang_name,
            "params": None,
            "decorators": [],
            "imports": [],
            "parent_class": None,
            "parser_used": "tree_sitter",
        }]
    return chunks


# ===============================
# 🐍 PYTHON AST FALLBACK (DEEP SEMANTICS)
# ===============================
def python_ast_parse(text: str):
    """
    Use Python's ast module to extract functions, classes, decorators, parameters,
    parent relationships, imports, and source segments.
    Returns list of chunk dicts similar to tree-sitter output.
    """
    try:
        tree = ast.parse(text)
    except Exception:
        return []

    src_lines = text.splitlines()
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                imports.append(ast.get_source_segment(text, node).strip())
            except Exception:
                if isinstance(node, ast.Import):
                    names = [n.name for n in node.names]
                    imports.append(f"import {', '.join(names)}")
                else:
                    module = getattr(node, "module", "")
                    names = [n.name for n in node.names]
                    imports.append(f"from {module} import {', '.join(names)}")

    chunks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            try:
                start_line = getattr(node, "lineno", 1)
                end_line = getattr(node, "end_lineno", start_line)
                try:
                    chunk_text = ast.get_source_segment(text, node) or "\n".join(src_lines[start_line - 1:end_line])
                except Exception:
                    chunk_text = "\n".join(src_lines[start_line - 1:end_line])
                node_type = type(node).__name__
                name = getattr(node, "name", None)
                params = []
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for a in node.args.args:
                        if hasattr(a, "arg"):
                            params.append(a.arg)
                decorators = []
                if getattr(node, "decorator_list", None):
                    for d in node.decorator_list:
                        try:
                            decorators.append(ast.unparse(d) if hasattr(ast, "unparse") else ast.dump(d))
                        except Exception:
                            decorators.append(ast.dump(d))
                parent_class = None
                for candidate in ast.walk(tree):
                    if isinstance(candidate, ast.ClassDef):
                        if getattr(candidate, "lineno", 0) <= start_line <= getattr(candidate, "end_lineno", 10**9):
                            if candidate is not node:
                                parent_class = getattr(candidate, "name", None)
                chunks.append({
                    "start_line": start_line,
                    "end_line": end_line,
                    "text": chunk_text,
                    "node_type": node_type,
                    "name": name,
                    "language": "python",
                    "params": params or None,
                    "decorators": decorators,
                    "imports": imports,
                    "parent_class": parent_class,
                    "parser_used": "python_ast",
                })
            except Exception:
                continue

    if not chunks:
        lines = src_lines
        chunks = [{
            "start_line": 1,
            "end_line": len(lines),
            "text": text,
            "node_type": "file",
            "name": None,
            "language": "python",
            "params": None,
            "decorators": [],
            "imports": imports,
            "parent_class": None,
            "parser_used": "python_ast",
        }]
    return chunks


# ===============================
# 🔄 WRAPPER
# ===============================
def extract_chunks(text: str, file_ext: str):
    """
    Try: tree-sitter -> python AST (if .py) -> regex fallback.
    Returns list of chunk dicts with standardized fields.
    """
    ext = file_ext.lower()
    ts_chunks = None
    try:
        ts_chunks = code_chunks_with_treesitter(text, ext)
        if ts_chunks:
            for c in ts_chunks:
                if "language" not in c:
                    c["language"] = EXT_TO_TS_LANG.get(ext, ext.lstrip('.'))
            print(f"✅ Using Tree-sitter for {ext}, chunks: {len(ts_chunks)}")
            return ts_chunks
        else:
            print(f"⚙️ Tree-sitter unavailable or produced no chunks for {ext}.")
    except Exception as e:
        print(f"⚠️ Error using Tree-sitter for {ext}: {e}")

    if ext == ".py":
        try:
            ast_chunks = python_ast_parse(text)
            if ast_chunks:
                print(f"🧠 Used Python AST parser, chunks: {len(ast_chunks)}")
                return ast_chunks
        except Exception as e:
            print(f"⚠️ Python AST fallback failed: {e}")

    print(f"🔁 Falling back to regex splitter for {ext}")
    return simple_function_split(text, language=EXT_TO_TS_LANG.get(ext, ext.lstrip('.')))
