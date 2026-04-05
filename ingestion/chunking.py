# chunking.py - Code chunking with multiple parsers

import ast
import os
import re
import threading
from functools import lru_cache
from typing import Any, Dict, List, Optional

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


MAX_CHUNK_LINES = 200
LARGE_FILE_LINE_THRESHOLD = 300
MAX_CHUNK_TOKENS_ESTIMATE = 1600
CHUNK_OVERLAP_LINES = 40
PARSER_DEBUG = os.getenv("INGEST_DEBUG_PARSERS", "").strip().lower() in {"1", "true", "yes", "on"}
_THREAD_LOCAL = threading.local()


def _approx_token_count(text: str) -> int:
    return max(1, len(text) // 4)


def _split_large_text(
    text: str,
    start_line: int,
    language: str,
    parser_used: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Split a large chunk into overlapping line windows."""
    lines = text.splitlines()
    if not lines:
        return []

    step = max(1, MAX_CHUNK_LINES - CHUNK_OVERLAP_LINES)
    base_metadata = dict(metadata or {})
    base_metadata.pop("text", None)
    base_metadata.pop("start_line", None)
    base_metadata.pop("end_line", None)
    base_metadata.pop("name", None)

    chunks = []
    for offset in range(0, len(lines), step):
        window = lines[offset:offset + MAX_CHUNK_LINES]
        if not window:
            continue

        chunk_start = start_line + offset
        chunk_end = chunk_start + len(window) - 1
        chunks.append({
            "start_line": chunk_start,
            "end_line": chunk_end,
            "text": "\n".join(window),
            "node_type": base_metadata.get("node_type", "chunk"),
            "name": None,
            "language": language,
            "parser_used": parser_used,
            "params": base_metadata.get("params"),
            "decorators": base_metadata.get("decorators", []),
            "imports": base_metadata.get("imports", []),
            "parent_class": base_metadata.get("parent_class"),
        })

        if chunk_end >= start_line + len(lines) - 1:
            break

    return chunks


def _is_chunk_too_large(chunk: Dict[str, Any]) -> bool:
    start_line = int(chunk.get("start_line", 1))
    end_line = int(chunk.get("end_line", start_line))
    line_count = max(0, end_line - start_line + 1)
    return (
        line_count > MAX_CHUNK_LINES
        or _approx_token_count(chunk.get("text", "")) > MAX_CHUNK_TOKENS_ESTIMATE
    )


def _normalize_chunks(chunks: List[Dict[str, Any]], language: str, parser_used: str) -> List[Dict[str, Any]]:
    """Ensure no chunk exceeds configured size limits."""
    normalized = []
    for chunk in chunks:
        if not _is_chunk_too_large(chunk):
            normalized.append(chunk)
            continue

        normalized.extend(
            _split_large_text(
                text=chunk.get("text", ""),
                start_line=int(chunk.get("start_line", 1)),
                language=chunk.get("language") or language,
                parser_used=chunk.get("parser_used", parser_used),
                metadata=chunk,
            )
        )
    return normalized


def simple_function_split(code: str, language: str = "unknown") -> List[Dict[str, Any]]:
    """
    Very simple heuristic splitter when tree-sitter/AST unavailable.
    Returns list of dicts with start_line, end_line, text, node_type, name, parser_used.
    """
    lines = code.splitlines()
    line_count = len(lines)
    boundaries = [0]

    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            boundaries.append(index)
        if re.match(r"^(export\s+)?function\s+\w+\s*\(", stripped) or re.match(r"^\w+\s*:\s*function\s*\(", stripped):
            boundaries.append(index)
        if re.match(r"^\w+\s*=\s*\(.*\)\s*=>", stripped):
            boundaries.append(index)

    boundaries = sorted(set(boundaries))
    chunks = []
    for idx, boundary in enumerate(boundaries):
        start = boundary
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else line_count
        text = "\n".join(lines[start:end]).strip()
        if not text:
            continue

        name = None
        first = lines[start].strip() if start < line_count else ""
        match = re.match(r"(def|class|function)\s+([A-Za-z0-9_]+)", first)
        if match:
            name = match.group(2)

        chunks.append({
            "start_line": start + 1,
            "end_line": end,
            "text": text,
            "node_type": "chunk",
            "name": name,
            "language": language,
            "parser_used": "regex_fallback",
        })

    if len(chunks) <= 1 and line_count > LARGE_FILE_LINE_THRESHOLD:
        return _split_large_text(code, 1, language, "regex_fallback")

    return _normalize_chunks(chunks, language, "regex_fallback")


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


@lru_cache(maxsize=None)
def _get_cached_language(lang_name: str):
    if not _HAS_TS_LANGS:
        return None
    try:
        return get_language(lang_name)
    except Exception:
        return None


def _get_thread_local_parser(lang_name: str):
    if not _HAS_TREE_SITTER:
        return None
    parser_cache = getattr(_THREAD_LOCAL, "parsers", None)
    if parser_cache is None:
        parser_cache = {}
        _THREAD_LOCAL.parsers = parser_cache

    parser = parser_cache.get(lang_name)
    if parser is not None:
        return parser

    language = _get_cached_language(lang_name)
    if language is None:
        return None

    try:
        parser = Parser()
        parser.set_language(language)
    except Exception:
        return None

    parser_cache[lang_name] = parser
    return parser


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

    parser = _get_thread_local_parser(lang_name)
    if parser is None:
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

    imports = []
    try:
        for match in re.finditer(r"^\s*(?:from\s+[\w\.]+\s+import|import\s+[\w\.]+)", text, flags=re.MULTILINE):
            imports.append(match.group(0).strip())
    except Exception:
        imports = []

    source_lines = text.splitlines()

    def walk(node, parent_stack=None):
        parent_stack = parent_stack or []
        if node.type in node_types_of_interest:
            try:
                chunk_text = _get_node_text(source_bytes, node)
            except Exception:
                chunk_text = ""

            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            name = extract_name(node)
            parent_class = None
            for parent in reversed(parent_stack):
                if parent.type in ("class_definition", "class_declaration"):
                    parent_class = extract_name(parent)
                    break

            params = None
            decorators = []
            try:
                first_line = chunk_text.splitlines()[0]
                sig_match = re.search(r"\((.*?)\)", first_line)
                if sig_match:
                    params = [param.strip() for param in sig_match.group(1).split(",") if param.strip()]
                for idx in range(max(0, start_line - 6), start_line - 1):
                    line = source_lines[idx].strip()
                    if line.startswith("@") or line.startswith("# decorator"):
                        decorators.append(line)
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

        for child in node.children:
            walk(child, parent_stack + [node])

    walk(root, [])
    if not chunks:
        return _split_large_text(text, 1, lang_name, "tree_sitter", {
            "node_type": "file",
            "params": None,
            "decorators": [],
            "imports": imports,
            "parent_class": None,
        })

    return _normalize_chunks(chunks, lang_name, "tree_sitter")


def python_ast_parse(text: str, tree: Optional[ast.AST] = None):
    """
    Use Python's ast module to extract functions, classes, decorators, parameters,
    parent relationships, imports, and source segments.
    Returns list of chunk dicts similar to tree-sitter output.
    """
    try:
        tree = tree or ast.parse(text)
    except Exception:
        return []

    source_lines = text.splitlines()
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                imports.append(ast.get_source_segment(text, node).strip())
            except Exception:
                if isinstance(node, ast.Import):
                    names = [entry.name for entry in node.names]
                    imports.append(f"import {', '.join(names)}")
                else:
                    module = getattr(node, "module", "")
                    names = [entry.name for entry in node.names]
                    imports.append(f"from {module} import {', '.join(names)}")

    class ChunkCollector(ast.NodeVisitor):
        def __init__(self):
            self.class_stack: List[str] = []
            self.collected: List[Dict[str, Any]] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.collected.append(self._build_chunk(node, "python", self.class_stack[-1] if self.class_stack else None))
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.collected.append(self._build_chunk(node, "python", self.class_stack[-1] if self.class_stack else None))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.collected.append(self._build_chunk(node, "python", self.class_stack[-1] if self.class_stack else None))
            self.generic_visit(node)

        def _build_chunk(self, node: ast.AST, language: str, parent_class: Optional[str]) -> Dict[str, Any]:
            start_line = getattr(node, "lineno", 1)
            end_line = getattr(node, "end_lineno", start_line)
            try:
                chunk_text = ast.get_source_segment(text, node) or "\n".join(source_lines[start_line - 1:end_line])
            except Exception:
                chunk_text = "\n".join(source_lines[start_line - 1:end_line])

            params = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    if hasattr(arg, "arg"):
                        params.append(arg.arg)

            decorators = []
            for decorator in getattr(node, "decorator_list", []):
                try:
                    decorators.append(ast.unparse(decorator) if hasattr(ast, "unparse") else ast.dump(decorator))
                except Exception:
                    decorators.append(ast.dump(decorator))

            return {
                "start_line": start_line,
                "end_line": end_line,
                "text": chunk_text,
                "node_type": type(node).__name__,
                "name": getattr(node, "name", None),
                "language": language,
                "params": params or None,
                "decorators": decorators,
                "imports": imports,
                "parent_class": parent_class,
                "parser_used": "python_ast",
            }

    collector = ChunkCollector()
    collector.visit(tree)

    if not collector.collected:
        return _split_large_text(text, 1, "python", "python_ast", {
            "node_type": "file",
            "params": None,
            "decorators": [],
            "imports": imports,
            "parent_class": None,
        })

    return _normalize_chunks(collector.collected, "python", "python_ast")


def extract_chunks(text: str, file_ext: str, syntax_tree: Optional[ast.AST] = None):
    """
    Try: tree-sitter -> python AST (if .py) -> regex fallback.
    Returns list of chunk dicts with standardized fields.
    """
    ext = file_ext.lower()
    try:
        ts_chunks = code_chunks_with_treesitter(text, ext)
        if ts_chunks:
            for chunk in ts_chunks:
                if "language" not in chunk:
                    chunk["language"] = EXT_TO_TS_LANG.get(ext, ext.lstrip("."))
            if PARSER_DEBUG:
                print(f"Using Tree-sitter for {ext}, chunks: {len(ts_chunks)}")
            return ts_chunks
        if PARSER_DEBUG:
            print(f"Tree-sitter unavailable or produced no chunks for {ext}.")
    except Exception as exc:
        print(f"Error using Tree-sitter for {ext}: {exc}")

    if ext == ".py":
        try:
            ast_chunks = python_ast_parse(text, tree=syntax_tree)
            if ast_chunks:
                if PARSER_DEBUG:
                    print(f"Used Python AST parser, chunks: {len(ast_chunks)}")
                return ast_chunks
        except Exception as exc:
            print(f"Python AST fallback failed: {exc}")

    if PARSER_DEBUG:
        print(f"Falling back to regex splitter for {ext}")
    return simple_function_split(text, language=EXT_TO_TS_LANG.get(ext, ext.lstrip(".")))
