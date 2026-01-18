# dataflow.py - Data flow analysis engine

import ast
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Definition:
    """Represents a definition (assignment) of a variable."""
    name: str
    line_number: int
    value_expr: Optional[str] = None  # Source of the assignment
    inferred_type: Optional[str] = None  # Type at this point
    constant_value: Optional[Any] = None  # If constant, the value
    is_parameter: bool = False  # If from function parameter
    is_import: bool = False  # If from import


@dataclass
class Use:
    """Represents a use (reference) of a variable."""
    name: str
    line_number: int
    context: str = "unknown"  # "call", "argument", "operand", "return", etc.
    inferred_type: Optional[str] = None  # Type expected at this use


@dataclass
class DefUseChain:
    """Links definitions to uses."""
    definition: Definition
    uses: List[Use] = field(default_factory=list)
    reaching_definitions: List[Definition] = field(default_factory=list)  # For data flow


class ControlFlowGraph:
    """Represents control flow within a function."""
    
    def __init__(self, function_name: str):
        self.function_name = function_name
        self.blocks: Dict[int, List[ast.stmt]] = defaultdict(list)  # line -> statements
        self.edges: List[tuple] = []  # (from_line, to_line)
        self.predecessors: Dict[int, List[int]] = defaultdict(list)
        self.successors: Dict[int, List[int]] = defaultdict(list)
        self.branch_points: Dict[int, tuple] = {}  # line -> (type, condition)
    
    def add_block(self, line_number: int, statements: List[ast.stmt]) -> None:
        """Add a basic block."""
        self.blocks[line_number] = statements
    
    def add_edge(self, from_line: int, to_line: int) -> None:
        """Add control flow edge."""
        self.edges.append((from_line, to_line))
        self.successors[from_line].append(to_line)
        self.predecessors[to_line].append(from_line)
    
    def add_branch(self, line_number: int, branch_type: str, condition: ast.expr) -> None:
        """Track branch point (if/while/for)."""
        self.branch_points[line_number] = (branch_type, condition)


class DataFlowAnalyzer(ast.NodeVisitor):
    """Analyze data flow within a function."""
    
    def __init__(self, function_node: ast.FunctionDef, source_code: str):
        self.function_node = function_node
        self.source_lines = source_code.splitlines()
        self.function_name = function_node.name
        self.cfg = ControlFlowGraph(function_node.name)
        
        # Tracking data
        self.definitions: Dict[str, List[Definition]] = defaultdict(list)
        self.uses: Dict[str, List[Use]] = defaultdict(list)
        self.def_use_chains: Dict[str, DefUseChain] = {}
        self.type_state: Dict[str, Optional[str]] = {}
        self.constant_values: Dict[str, Optional[Any]] = {}
        self.type_by_line: Dict[int, Dict[str, str]] = defaultdict(dict)
        
        # Extract parameters as initial definitions
        self._extract_parameters()
    
    def _extract_parameters(self) -> None:
        """Extract function parameters as definitions."""
        for arg in self.function_node.args.args:
            param_name = arg.arg
            param_type = None
            if arg.annotation:
                param_type = ast.unparse(arg.annotation) if hasattr(ast, "unparse") else ast.dump(arg.annotation)
            
            defn = Definition(
                name=param_name,
                line_number=self.function_node.lineno,
                inferred_type=param_type,
                is_parameter=True
            )
            self.definitions[param_name].append(defn)
            self.type_state[param_name] = param_type
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Traverse function body."""
        for stmt in node.body:
            self.visit(stmt)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Traverse async function body."""
        self.visit_FunctionDef(node)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """Track assignments."""
        for target in node.targets:
            self._process_assignment_target(target, node.value, node.lineno)
        self.generic_visit(node)
    
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Track annotated assignments."""
        if node.target and isinstance(node.target, ast.Name):
            var_name = node.target.id
            inferred_type = ast.unparse(node.annotation) if hasattr(ast, "unparse") else ast.dump(node.annotation)
            constant_val = self._extract_constant_value(node.value) if node.value else None
            
            defn = Definition(
                name=var_name,
                line_number=node.lineno,
                value_expr=ast.unparse(node.value) if node.value and hasattr(ast, "unparse") else None,
                inferred_type=inferred_type,
                constant_value=constant_val
            )
            self.definitions[var_name].append(defn)
            self.type_state[var_name] = inferred_type
            self.constant_values[var_name] = constant_val
            self.type_by_line[node.lineno][var_name] = inferred_type
        
        self.generic_visit(node)
    
    def visit_For(self, node: ast.For) -> None:
        """Track loop variables and branch."""
        if isinstance(node.target, ast.Name):
            var_name = node.target.id
            loop_type = "Any"
            defn = Definition(
                name=var_name,
                line_number=node.lineno,
                inferred_type=loop_type
            )
            self.definitions[var_name].append(defn)
            self.type_state[var_name] = loop_type
        
        self.cfg.add_branch(node.lineno, "for", node.target)
        
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
    
    def visit_If(self, node: ast.If) -> None:
        """Track conditional branches."""
        self.cfg.add_branch(node.lineno, "if", node.test)
        
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
    
    def visit_Name(self, node: ast.Name) -> None:
        """Track variable uses."""
        if isinstance(node.ctx, ast.Load):
            use = Use(
                name=node.id,
                line_number=node.lineno,
                inferred_type=self.type_state.get(node.id)
            )
            self.uses[node.id].append(use)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call) -> None:
        """Track function calls and their arguments."""
        if isinstance(node.func, ast.Name):
            use = Use(
                name=node.func.id,
                line_number=node.lineno,
                context="call"
            )
            self.uses[node.func.id].append(use)
        
        # Track arguments as uses
        for arg in node.args:
            if isinstance(arg, ast.Name):
                use = Use(
                    name=arg.id,
                    line_number=node.lineno,
                    context="argument",
                    inferred_type=self.type_state.get(arg.id)
                )
                self.uses[arg.id].append(use)
        
        self.generic_visit(node)
    
    def visit_Return(self, node: ast.Return) -> None:
        """Track return value uses."""
        if node.value and isinstance(node.value, ast.Name):
            use = Use(
                name=node.value.id,
                line_number=node.lineno,
                context="return",
                inferred_type=self.type_state.get(node.value.id)
            )
            self.uses[node.value.id].append(use)
        
        self.generic_visit(node)
    
    def _process_assignment_target(self, target: ast.expr, value: ast.expr, lineno: int) -> None:
        """Process assignment target(s)."""
        if isinstance(target, ast.Name):
            var_name = target.id
            inferred_type = self._infer_type_from_value(value)
            constant_val = self._extract_constant_value(value)
            
            defn = Definition(
                name=var_name,
                line_number=lineno,
                value_expr=ast.unparse(value) if hasattr(ast, "unparse") else None,
                inferred_type=inferred_type,
                constant_value=constant_val
            )
            self.definitions[var_name].append(defn)
            self.type_state[var_name] = inferred_type
            self.constant_values[var_name] = constant_val
            self.type_by_line[lineno][var_name] = inferred_type
        
        elif isinstance(target, (ast.Tuple, ast.List)):
            # Handle unpacking
            for elt in target.elts:
                self._process_assignment_target(elt, value, lineno)
    
    def _infer_type_from_value(self, value: ast.expr) -> Optional[str]:
        """Infer type from value expression."""
        if isinstance(value, ast.Constant):
            if isinstance(value.value, int):
                return "int"
            elif isinstance(value.value, str):
                return "str"
            elif isinstance(value.value, bool):
                return "bool"
            elif isinstance(value.value, float):
                return "float"
            elif value.value is None:
                return "None"
        elif isinstance(value, ast.List):
            return "list"
        elif isinstance(value, ast.Dict):
            return "dict"
        elif isinstance(value, ast.Tuple):
            return "tuple"
        elif isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return value.func.id
        elif isinstance(value, ast.BinOp):
            left_type = self._infer_type_from_value(value.left)
            right_type = self._infer_type_from_value(value.right)
            if left_type == right_type:
                return left_type
            return "Any"
        elif isinstance(value, ast.Name):
            return self.type_state.get(value.id, "Any")
        
        return "Any"
    
    def _extract_constant_value(self, value: ast.expr) -> Optional[Any]:
        """Extract constant value if statically determinable."""
        try:
            if isinstance(value, ast.Constant):
                return value.value
            elif isinstance(value, ast.Num):  # Python < 3.8
                return value.n
            elif isinstance(value, ast.Str):  # Python < 3.8
                return value.s
            elif isinstance(value, ast.List):
                return [self._extract_constant_value(elt) for elt in value.elts if isinstance(elt, ast.Constant)]
            elif isinstance(value, ast.Tuple):
                return tuple(self._extract_constant_value(elt) for elt in value.elts if isinstance(elt, ast.Constant))
        except Exception:
            pass
        return None
    
    def build_def_use_chains(self) -> None:
        """Build definition-use chains with reaching definitions."""
        for var_name, definitions in self.definitions.items():
            uses_list = self.uses.get(var_name, [])
            
            # For each definition, find which uses it reaches
            for defn in definitions:
                chain = DefUseChain(definition=defn)
                
                # Simple heuristic: a definition reaches a use if:
                # 1. Use is after definition
                # 2. No other definition between them (simplified)
                for use in uses_list:
                    if use.line_number > defn.line_number:
                        chain.uses.append(use)
                
                self.def_use_chains[f"{var_name}@{defn.line_number}"] = chain
    
    def analyze(self) -> Dict[str, Any]:
        """Run complete data flow analysis."""
        self.visit(self.function_node)
        self.build_def_use_chains()
        
        return {
            "function_name": self.function_name,
            "definitions": {
                var: [
                    {
                        "line": d.line_number,
                        "type": d.inferred_type,
                        "constant": d.constant_value,
                        "is_param": d.is_parameter,
                        "value_expr": d.value_expr,
                    }
                    for d in defs
                ]
                for var, defs in self.definitions.items()
            },
            "uses": {
                var: [
                    {
                        "line": u.line_number,
                        "context": u.context,
                        "type": u.inferred_type,
                    }
                    for u in uses_list
                ]
                for var, uses_list in self.uses.items()
            },
            "def_use_chains": {
                chain_id: {
                    "definition": {
                        "line": chain.definition.line_number,
                        "type": chain.definition.inferred_type,
                        "constant": chain.definition.constant_value,
                    },
                    "uses": [
                        {"line": u.line_number, "context": u.context}
                        for u in chain.uses
                    ]
                }
                for chain_id, chain in self.def_use_chains.items()
            },
            "type_at_line": dict(self.type_by_line),
            "constants": {var: val for var, val in self.constant_values.items() if val is not None},
            "control_flow": {
                "branches": [
                    {
                        "line": line,
                        "type": branch_type,
                        "condition": ast.unparse(cond) if hasattr(ast, "unparse") else ast.dump(cond),
                    }
                    for line, (branch_type, cond) in self.cfg.branch_points.items()
                ]
            },
        }


def extract_function_dataflow(file_path: str, source_code: str) -> Dict[str, Any]:
    """
    Extract data flow analysis for all functions in a file.
    Returns analysis results keyed by function name.
    """
    try:
        tree = ast.parse(source_code)
    except Exception as e:
        print(f"⚠️ Failed to parse {file_path}: {e}")
        return {}
    
    dataflow_results = {}
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                analyzer = DataFlowAnalyzer(node, source_code)
                analysis = analyzer.analyze()
                dataflow_results[node.name] = analysis
            except Exception as e:
                print(f"⚠️ Data flow analysis failed for {node.name} in {file_path}: {e}")
    
    return dataflow_results
