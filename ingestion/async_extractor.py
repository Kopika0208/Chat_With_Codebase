"""Extract async and background-execution patterns from Python source files."""

import ast
from typing import Dict, Any, List


class AsyncPatternVisitor(ast.NodeVisitor):
    """Collect common async/background execution patterns."""

    def __init__(self):
        self.patterns: List[Dict[str, Any]] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.patterns.append({
            "pattern_type": "async_function",
            "name": node.name,
            "line": node.lineno,
            "details": {
                "decorators": [self._safe_unparse(dec) for dec in node.decorator_list],
            },
        })
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:
        self.patterns.append({
            "pattern_type": "await",
            "name": self._safe_unparse(node.value),
            "line": node.lineno,
            "details": {},
        })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._call_name(node.func)
        pattern_type = None

        if call_name in {"asyncio.create_task", "create_task"}:
            pattern_type = "asyncio_create_task"
        elif call_name in {"threading.Thread", "Thread"}:
            pattern_type = "thread_spawn"
        elif call_name and any(token in call_name for token in ("delay", "apply_async", "enqueue", "submit")):
            pattern_type = "background_dispatch"

        if pattern_type:
            self.patterns.append({
                "pattern_type": pattern_type,
                "name": call_name,
                "line": node.lineno,
                "details": {
                    "args": [self._safe_unparse(arg) for arg in node.args[:5]],
                },
            })

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        decorator_names = [self._safe_unparse(dec) for dec in node.decorator_list]
        if any(self._looks_like_background_decorator(name) for name in decorator_names):
            self.patterns.append({
                "pattern_type": "task_decorator",
                "name": node.name,
                "line": node.lineno,
                "details": {
                    "decorators": decorator_names,
                },
            })
        self.generic_visit(node)

    def _call_name(self, func: ast.AST) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            base = self._call_name(func.value)
            return f"{base}.{func.attr}" if base else func.attr
        return ""

    def _safe_unparse(self, node: ast.AST) -> str:
        if hasattr(ast, "unparse"):
            try:
                return ast.unparse(node)
            except Exception:
                return ast.dump(node)
        return ast.dump(node)

    def _looks_like_background_decorator(self, decorator_name: str) -> bool:
        lowered = decorator_name.lower()
        return any(token in lowered for token in ("celery", "task", "background", "job", "shared_task"))


def extract_async_patterns(file_path: str, source_code: str, tree: ast.AST = None) -> Dict[str, Any]:
    """Extract async/background patterns from a Python file."""
    try:
        tree = tree or ast.parse(source_code)
    except Exception as e:
        print(f"⚠️ Failed to parse async patterns in {file_path}: {e}")
        return {}

    visitor = AsyncPatternVisitor()
    visitor.visit(tree)

    if not visitor.patterns:
        return {}

    return {
        "file_path": file_path,
        "patterns": visitor.patterns,
        "pattern_count": len(visitor.patterns),
    }
