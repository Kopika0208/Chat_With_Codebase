# ingest.py
import os
import re
import ast
from pathlib import Path
from datetime import timezone
from dotenv import load_dotenv
from git import Repo
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# ===============================
# 🌲 TREE-SITTER IMPORTS (optional)
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

    # helper to extract a candidate identifier/name for node
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
        # naive regex to find import lines; better than nothing
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
            # small regex to extract signature from chunk_text first line(s)
            try:
                first_line = chunk_text.splitlines()[0]
                sig_match = re.search(r'\((.*?)\)', first_line)
                if sig_match:
                    params = [p.strip() for p in sig_match.group(1).split(",") if p.strip()]
                # decorators: look above start_line in original source
                # fetch up to 5 lines above start_line
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
                # best-effort: reconstruct
                if isinstance(node, ast.Import):
                    names = [n.name for n in node.names]
                    imports.append(f"import {', '.join(names)}")
                else:
                    module = getattr(node, "module", "")
                    names = [n.name for n in node.names]
                    imports.append(f"from {module} import {', '.join(names)}")

    # collect functions and classes with parent info
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
                # parameters
                params = []
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for a in node.args.args:
                        if hasattr(a, "arg"):
                            params.append(a.arg)
                # decorators
                decorators = []
                if getattr(node, "decorator_list", None):
                    for d in node.decorator_list:
                        try:
                            decorators.append(ast.unparse(d) if hasattr(ast, "unparse") else ast.dump(d))
                        except Exception:
                            decorators.append(ast.dump(d))
                # parent class: walk parents by scanning enclosing ClassDef via lineno
                parent_class = None
                # naive: find nearest ClassDef that spans this node
                for candidate in ast.walk(tree):
                    if isinstance(candidate, ast.ClassDef):
                        if getattr(candidate, "lineno", 0) <= start_line <= getattr(candidate, "end_lineno", 10**9):
                            # ensure it's an enclosing class
                            if candidate is not node:
                                # choose the deepest / nearest one
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

    # if nothing found, return whole file
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
    # try tree-sitter first (best for many languages)
    ts_chunks = None
    try:
        ts_chunks = code_chunks_with_treesitter(text, ext)
        if ts_chunks:
            # ensure language field exists
            for c in ts_chunks:
                if "language" not in c:
                    c["language"] = EXT_TO_TS_LANG.get(ext, ext.lstrip('.'))
            print(f"✅ Using Tree-sitter for {ext}, chunks: {len(ts_chunks)}")
            return ts_chunks
        else:
            print(f"⚙️ Tree-sitter unavailable or produced no chunks for {ext}.")
    except Exception as e:
        print(f"⚠️ Error using Tree-sitter for {ext}: {e}")

    # if Python, try AST fallback
    if ext == ".py":
        try:
            ast_chunks = python_ast_parse(text)
            if ast_chunks:
                print(f"🧠 Used Python AST parser, chunks: {len(ast_chunks)}")
                return ast_chunks
        except Exception as e:
            print(f"⚠️ Python AST fallback failed: {e}")

    # final fallback: simple regex-based split
    print(f"🔁 Falling back to regex splitter for {ext}")
    return simple_function_split(text, language=EXT_TO_TS_LANG.get(ext, ext.lstrip('.')))

# ===============================
# CONFIG
# ===============================
load_dotenv()
TARGET_REPO_DIR = "repos/myrepo"
VECTOR_DIR = "data/vector_store"
EXTENSIONS = ('.py', '.js', '.java', '.ts', '.md', '.txt', '.go', '.cpp', '.c', '.h', '.rs')
EMBED_MODEL = "thenlper/gte-base"

# ===============================
# HELPERS
# ===============================
def clone_or_open_repo(repo_url: str, target_dir: str = TARGET_REPO_DIR) -> str:
    if repo_url.startswith("http"):
        if os.path.exists(target_dir):
            print("♻️ Repo exists — removing for fresh clone.")
            os.system(f"rm -rf {target_dir}")
        print(f"📥 Cloning {repo_url} → {target_dir}")
        Repo.clone_from(repo_url, target_dir)
    return os.path.abspath(target_dir)

def list_repo_files(repo_path: str):
    for root, _, files in os.walk(repo_path):
        if any(ignored in root for ignored in [".git", "venv", "node_modules", "__pycache__"]):
            continue
        for f in files:
            if f.endswith(EXTENSIONS):
                yield os.path.join(root, f)

def get_commit_info(repo_path, file_path):
    try:
        repo = Repo(repo_path)
        rel = os.path.relpath(file_path, repo_path)
        commit = next(repo.iter_commits(paths=rel, max_count=1))
        try:
            dt = commit.committed_datetime.astimezone(timezone.utc).isoformat()
        except Exception:
            dt = None
        return commit.hexsha[:7], commit.message.strip().split("\n")[0], dt
    except Exception:
        return "unknown", "No commit message found", None

# ===============================
# 🚀 INGEST PIPELINE
# ===============================
def ingest_repo(repo_url_or_path: str):
    repo_path = clone_or_open_repo(repo_url_or_path)
    documents = []

    print(f"🔍 Scanning repository: {repo_path}")

    for file_path in list_repo_files(repo_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if not content.strip():
                continue

            ext = os.path.splitext(file_path)[1].lower()
            chunks = extract_chunks(content, ext)
            commit_sha, commit_msg, commit_date = get_commit_info(repo_path, file_path)
            rel_path = os.path.relpath(file_path, repo_path)

            for c in chunks:
                # ensure mandatory fields present
                doc_metadata = {
                    "path": rel_path,
                    "abs_path": file_path,
                    "start_line": int(c.get("start_line", 1)),
                    "end_line": int(c.get("end_line", c.get("start_line", 1))),
                    "commit_sha": commit_sha,
                    "commit_message": commit_msg,
                    "commit_date": commit_date,
                    "node_type": c.get("node_type"),
                    "symbol_name": c.get("name"),
                    "language": c.get("language") or EXT_TO_TS_LANG.get(ext, ext.lstrip('.')),
                    "parser_used": c.get("parser_used", "regex_fallback"),
                    # extended AST semantics (may be None)
                    "params": c.get("params"),
                    "decorators": c.get("decorators"),
                    "imports": c.get("imports"),
                    "parent_class": c.get("parent_class"),
                }
                doc = Document(
                    page_content=c.get("text", "").strip(),
                    metadata=doc_metadata,
                )
                documents.append(doc)

            used_parser = chunks[0].get("parser_used") if chunks else "unknown"
            print(f"✅ Processed {file_path} using {used_parser} ({len(chunks)} chunks)")

        except Exception as e:
            print(f"⚠️ Skipped {file_path}: {e}")

    print(f"✅ Loaded {len(documents)} chunks total from {repo_path}")
    if not documents:
        print("⚠️ No documents to embed; aborting ingestion.")
        return

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = FAISS.from_documents(documents, embeddings)

    os.makedirs(VECTOR_DIR, exist_ok=True)
    vectorstore.save_local(VECTOR_DIR)
    print(f"💾 Saved FAISS vector store to `{VECTOR_DIR}`")

# ===============================
# CLI
# ===============================
if __name__ == "__main__":
    repo_url = input("🔗 Enter GitHub repo URL or local path: ").strip()
    ingest_repo(repo_url)
