import ast
import os
import re
from typing import List, Dict

# ===============================
# Tree-sitter imports (optional)
# ===============================
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
def simple_function_split(code: str, language: str = "unknown") -> List[Dict]:
    """
    Very simple heuristic splitter when AST is unavailable.
    Guaranteed fallback — never crashes.
    """
    lines = code.splitlines()
    n = len(lines)
    boundaries = [0]

    for i, ln in enumerate(lines):
        s = ln.strip()

        # Python
        if s.startswith("def ") or s.startswith("class "):
            boundaries.append(i)

        # Java / C / C++
        if re.match(r'^(public|private|protected)?\s*(static)?\s*\w+\s+\w+\s*\(', s):
            boundaries.append(i)

        # JS / TS
        if re.match(r'^(export\s+)?function\s+\w+\s*\(', s):
            boundaries.append(i)

    boundaries = sorted(set(boundaries))
    chunks = []

    for i, b in enumerate(boundaries):
        start = b
        end = boundaries[i + 1] if i + 1 < len(boundaries) else n
        text = "\n".join(lines[start:end]).strip()
        if not text:
            continue

        name = None
        first = lines[start].strip()
        m = re.search(r'([A-Za-z_][A-Za-z0-9_]*)\s*\(', first)
        if m:
            name = m.group(1)

        chunks.append({
            "start_line": start + 1,
            "end_line": end,
            "text": text,
            "node_type": "chunk",
            "symbol_name": name,
            "language": language,
            "parser_used": "regex_fallback",
        })

    return chunks


# ===============================
# ⚙️ TREE-SITTER CONFIG
# ===============================
EXT_TO_TS_LANG = {
    ".py": "python",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
}

TS_NODE_TYPES = {
    "python": ["function_definition", "class_definition"],
    "java": ["method_declaration", "class_declaration"],
    "c": ["function_definition"],
    "cpp": ["function_definition", "class_specifier"],
    "javascript": ["function_declaration", "method_definition", "class_declaration"],
    "typescript": ["function_declaration", "method_definition", "class_declaration"],
    "go": ["function_declaration", "method_declaration"],
    "rust": ["function_item", "impl_item", "struct_item"],
}


def _get_node_text(src: bytes, node):
    return src[node.start_byte:node.end_byte].decode(errors="ignore")


# ===============================
# 🧠 TREE-SITTER CHUNKING
# ===============================
def code_chunks_with_treesitter(text: str, file_ext: str) -> List[Dict]:
    if not _HAS_TREE_SITTER or not _HAS_TS_LANGS:
        return []

    lang = EXT_TO_TS_LANG.get(file_ext)
    if not lang:
        return []

    try:
        language = get_language(lang)
        parser = Parser()
        parser.set_language(language)
    except Exception:
        return []

    src = text.encode()
    tree = parser.parse(src)
    root = tree.root_node
    node_types = TS_NODE_TYPES.get(lang, [])
    chunks = []

    def extract_name(node):
        for c in node.children:
            if c.type in ("identifier", "name"):
                return _get_node_text(src, c)
        return None

    def walk(node, parents):
        if node.type in node_types:
            start = node.start_point[0] + 1
            end = node.end_point[0] + 1
            name = extract_name(node)

            parent_class = None
            for p in reversed(parents):
                if p.type in ("class_definition", "class_declaration", "class_specifier"):
                    parent_class = extract_name(p)
                    break

            chunks.append({
                "start_line": start,
                "end_line": end,
                "text": _get_node_text(src, node),
                "node_type": node.type,
                "symbol_name": name,
                "language": lang,
                "parent_class": parent_class,
                "parser_used": "tree_sitter",
            })

        for c in node.children:
            walk(c, parents + [node])

    walk(root, [])
    return chunks


# ===============================
# 🐍 PYTHON AST (PRIMARY FOR PY)
# ===============================
def python_ast_parse(text: str) -> List[Dict]:
    try:
        tree = ast.parse(text)
    except Exception:
        return []

    lines = text.splitlines()
    chunks = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            chunks.append({
                "start_line": start,
                "end_line": end,
                "text": "\n".join(lines[start - 1:end]),
                "node_type": type(node).__name__,
                "symbol_name": node.name,
                "language": "python",
                "parser_used": "python_ast",
            })

    return chunks


# ===============================
# 🔄 MAIN ENTRY POINT
# ===============================
def extract_chunks(text: str, file_path: str) -> List[Dict]:
    """
    FINAL ORDER:
    1️⃣ Python AST
    2️⃣ Tree-sitter (Java, C, C++, JS, TS, Go, Rust)
    3️⃣ Regex fallback (any language)
    """
    ext = os.path.splitext(file_path)[1].lower()
    language = EXT_TO_TS_LANG.get(ext, ext.lstrip("."))

    # Python first
    if ext == ".py":
        py_chunks = python_ast_parse(text)
        if py_chunks:
            return py_chunks

    # Tree-sitter for supported languages
    ts_chunks = code_chunks_with_treesitter(text, ext)
    if ts_chunks:
        return ts_chunks

    # Always-safe fallback
    return simple_function_split(text, language)