"""
Codebase analyzer for onboarding.
Extracts insights from call graphs, symbol tables, and file structures.
"""

import os
import json
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque


class CodebaseAnalyzer:
    """Analyzes codebase structure and relationships using all available data sources."""
    
    def __init__(self, call_graph: Dict, symbol_table: Dict, repo_path: str, root_dir: str, 
                 vectorstore=None, knowledge_graph: Dict = None, dataflow_data: Dict = None):
        """
        Initialize analyzer with comprehensive codebase data.
        
        Args:
            call_graph: Dictionary mapping function names to their callees
            symbol_table: Dictionary with symbol metadata (functions, classes, files)
            repo_path: Path to the repository data
            root_dir: Root directory of the actual source code
            vectorstore: FAISS vectorstore with document metadata (optional)
            knowledge_graph: Knowledge graph for semantic relationships (optional)
            dataflow_data: Dataflow analysis results (optional)
        """
        self.call_graph = call_graph or {}
        self.repo_path = repo_path
        self.root_dir = root_dir
        self.vectorstore = vectorstore
        self.knowledge_graph = knowledge_graph or {}
        self.dataflow_data = dataflow_data or {}
        
        # Parse symbol table - handle both flat and nested formats
        self.symbol_table = self._parse_symbol_table(symbol_table or {})
        
        # Extract files from vectorstore if available
        self.vectorstore_files = set()
        if vectorstore:
            try:
                all_docs = list(vectorstore.docstore._dict.values())
                for doc in all_docs:
                    file_path = doc.metadata.get("path", "")
                    if file_path:
                        self.vectorstore_files.add(file_path)
            except Exception as e:
                print(f"⚠️ Warning: Could not extract files from vectorstore: {e}")
        
        # Build enriched symbol relationships using knowledge graph
        self._build_enhanced_relationships()
    
    def _parse_symbol_table(self, symbol_table: Dict) -> Dict:
        """
        Parse symbol table - handles both flat and nested formats.
        Nested format has 'global_index' and 'file_symbols' keys.
        Global symbols is indexed by name -> list of occurrences.
        """
        if not symbol_table:
            return {}
        
        # Check if it's nested format (has 'global_index' and 'file_symbols')
        if 'global_index' in symbol_table:
            flattened = {}
            
            # Add global symbols
            global_symbols = symbol_table['global_index'].get('global_symbols', {})
            if isinstance(global_symbols, dict):
                for symbol_name, occurrences in global_symbols.items():
                    # Each symbol can have multiple occurrences (in different files)
                    # Use the first occurrence as the primary definition
                    if isinstance(occurrences, list) and len(occurrences) > 0:
                        first_occurrence = occurrences[0]
                        if isinstance(first_occurrence, dict):
                            flattened[symbol_name] = {
                                "name": symbol_name,
                                "file": first_occurrence.get("file", "unknown"),
                                "type": self._infer_symbol_type(first_occurrence, symbol_name),
                                "kind": first_occurrence.get("kind", "unknown"),
                                "start_line": first_occurrence.get("line", 0),
                                "end_line": first_occurrence.get("line", 0),
                                "is_private": first_occurrence.get("is_private", False),
                                "occurrences": len(occurrences),
                            }
                    elif isinstance(occurrences, dict):
                        # Single dict instead of list
                        flattened[symbol_name] = {
                            "name": symbol_name,
                            "file": occurrences.get("file", "unknown"),
                            "type": self._infer_symbol_type(occurrences, symbol_name),
                            "kind": occurrences.get("kind", "unknown"),
                            "start_line": occurrences.get("line", 0),
                            "end_line": occurrences.get("line", 0),
                            "is_private": occurrences.get("is_private", False),
                        }
            
            return flattened
        
        # Already in flat format - normalize it
        normalized = {}
        for symbol_name, symbol_info in symbol_table.items():
            if isinstance(symbol_info, dict):
                normalized[symbol_name] = symbol_info
        return normalized
    
    def _infer_symbol_type(self, symbol_info: Dict, symbol_name: str) -> str:
        """Infer symbol type from kind and name patterns."""
        kind = symbol_info.get("kind", "unknown")
        
        # Map kinds to types
        kind_mapping = {
            "function": "function",
            "method": "method",
            "class": "class",
            "import": "import",
            "variable": "variable",
            "constant": "constant",
            "module": "module",
        }
        
        if kind in kind_mapping:
            return kind_mapping[kind]
        
        # Infer from naming conventions
        if symbol_name.isupper() and "_" in symbol_name:
            return "constant"
        elif symbol_name.startswith("_"):
            return "variable"
        elif "class" in kind.lower():
            return "class"
        elif "def" in kind.lower() or "function" in kind.lower():
            return "function"
        else:
            return kind if kind != "unknown" else "variable"
    
    def _build_enhanced_relationships(self):
        """Build enhanced relationships using knowledge graph and dataflow data."""
        # Knowledge graph provides semantic relationships beyond just function calls
        self.semantic_relationships = {}
        
        if self.knowledge_graph:
            # Extract relationships from knowledge graph nodes and edges
            try:
                for node_id, node_data in self.knowledge_graph.items():
                    if isinstance(node_data, dict):
                        self.semantic_relationships[node_id] = {
                            "type": node_data.get("type", "unknown"),
                            "related": node_data.get("related", []),
                            "properties": node_data.get("properties", {}),
                        }
            except Exception as e:
                print(f"⚠️ Could not extract knowledge graph relationships: {e}")
        
        # Dataflow analysis shows data dependencies (more than just control flow)
        self.dataflow_relationships = {}
        if self.dataflow_data:
            try:
                for func_name, flows in self.dataflow_data.items():
                    if isinstance(flows, dict):
                        self.dataflow_relationships[func_name] = {
                            "reads": flows.get("reads", []),
                            "writes": flows.get("writes", []),
                            "depends_on": flows.get("depends_on", []),
                        }
            except Exception as e:
                print(f"⚠️ Could not extract dataflow relationships: {e}")
        
    def get_project_stats(self) -> Dict:
        """Extract project overview statistics using all available symbol data."""
        total_files = 0
        total_functions = 0  # From call graph (most accurate)
        total_methods = 0    # From symbol table
        total_classes = 0
        total_symbols = 0
        
        # Count symbols from symbol table (now properly parsed)
        functions_by_file = defaultdict(set)
        methods_by_file = defaultdict(set)
        classes_by_file = defaultdict(set)
        all_symbols_by_file = defaultdict(set)
        
        for symbol_name, symbol_info in self.symbol_table.items():
            if isinstance(symbol_info, dict):
                file_path = symbol_info.get("file", "unknown")
                node_type = symbol_info.get("type", "unknown")
                kind = symbol_info.get("kind", "unknown")
                
                all_symbols_by_file[file_path].add(symbol_name)
                total_symbols += 1
                
                # Count by type - methods are also functions
                if node_type == "function" or kind == "function":
                    functions_by_file[file_path].add(symbol_name)
                    total_functions += 1
                elif node_type == "method" or kind == "method":
                    methods_by_file[file_path].add(symbol_name)
                    total_methods += 1
                elif node_type == "class" or kind == "class":
                    classes_by_file[file_path].add(symbol_name)
                    total_classes += 1
        
        # Use call graph count as ground truth for total functions
        actual_function_count = len(self.call_graph) if self.call_graph else (total_functions + total_methods)
        
        # Build comprehensive file list
        all_files = set()
        
        # From symbol table
        all_files.update(functions_by_file.keys())
        all_files.update(methods_by_file.keys())
        all_files.update(classes_by_file.keys())
        all_files.update(all_symbols_by_file.keys())
        
        # From vectorstore as fallback/supplement
        if self.vectorstore_files:
            all_files.update(self.vectorstore_files)
        
        total_files = len(all_files)
        
        return {
            "total_files": total_files,
            "total_functions": actual_function_count,  # From call graph
            "total_methods": total_methods,
            "total_classes": total_classes,
            "total_symbols": total_symbols,
            "functions_by_file": dict(functions_by_file),
            "methods_by_file": dict(methods_by_file),
            "classes_by_file": dict(classes_by_file),
            "all_files": sorted(all_files),
        }
    
    def _lookup_line_info(self, func_name: str) -> tuple:
        """Look up line numbers for a function from symbol table."""
        # Try direct lookup first
        if func_name in self.symbol_table:
            info = self.symbol_table[func_name]
            if isinstance(info, dict):
                start = info.get("start_line", 0)
                end = info.get("end_line", 0)
                # If end_line is 0 but start_line is set, set end = start
                if end == 0 and start > 0:
                    end = start
                return (start, end)
        
        # Try short name (last part after :)
        short_name = func_name.split(':')[-1] if ':' in func_name else func_name
        if short_name in self.symbol_table:
            info = self.symbol_table[short_name]
            if isinstance(info, dict):
                start = info.get("start_line", 0)
                end = info.get("end_line", 0)
                if end == 0 and start > 0:
                    end = start
                return (start, end)
        
        return (0, 0)
    
    def get_entry_points(self) -> List[Dict]:
        """
        Identify probable entry points using multiple strategies:
        1. Call graph analysis (functions with low in-degree or high out-degree)
        2. Naming patterns (main, app, route, handler)
        3. Knowledge graph hubs
        """
        entry_points = []
        added_names = set()
        
        # Strategy 1: Use call graph directly - it has actual function relationships
        if self.call_graph:
            # Calculate in-degree for all functions in call graph
            in_degree = defaultdict(int)
            out_degree = defaultdict(int)
            
            for caller, callees in self.call_graph.items():
                # Handle both list and dict callees
                callees_list = callees if isinstance(callees, list) else (list(callees.values()) if isinstance(callees, dict) else [])
                out_degree[caller] = len(callees_list)
                for callee in callees_list:
                    in_degree[callee] += 1
            
            # Entry points: functions called rarely OR high out-degree (orchestrators)
            for func_name, out_count in out_degree.items():
                in_count = in_degree[func_name]
                
                # Extract short name for pattern matching
                name_parts = func_name.split(':')
                short_name = name_parts[-1].lower() if name_parts else func_name.lower()
                
                # Check if it looks like an entry point
                looks_like_entry = any(pattern in short_name for pattern in ['main', 'run', 'start', 'app', 'route', 'home', 'entry', 'serve', 'cli', 'handler'])
                
                # Is entry if: has entry-like name, OR low in-degree with outgoing calls, OR orchestrator with few callers
                is_entry = (
                    looks_like_entry or  # Naming pattern
                    (in_count <= 1 and out_count > 0) or  # Low in-degree entry point
                    (out_count >= 3 and in_count <= 2)  # High out-degree orchestrator
                )
                
                if is_entry:
                    # Look up actual line numbers
                    start_line, end_line = self._lookup_line_info(short_name)
                    
                    entry_points.append({
                        "name": func_name,
                        "file": name_parts[0] + ':' + name_parts[1] if len(name_parts) > 1 else 'unknown',
                        "type": "function",
                        "start_line": start_line,
                        "end_line": end_line,
                        "callers": in_count,
                        "callees": out_count,
                    })
                    added_names.add(func_name)
        
        # Strategy 2: Add symbol table functions that match entry patterns and weren't in call graph
        for symbol_name, symbol_info in self.symbol_table.items():
            if symbol_name not in added_names and isinstance(symbol_info, dict):
                if symbol_info.get("kind") in ["function", "method", "def"] or symbol_info.get("type") == "function":
                    name_lower = symbol_name.lower()
                    if any(pattern in name_lower for pattern in ['main', 'app', '__main__', 'run', 'start', 'entry', 'route']):
                        entry_points.append({
                            "name": symbol_name,
                            "file": symbol_info.get("file", "unknown"),
                            "type": "function",
                            "start_line": symbol_info.get("start_line", 0),
                            "end_line": symbol_info.get("end_line", 0),
                            "callers": 0,
                            "callees": 0,
                        })
                        added_names.add(symbol_name)
        
        # Remove duplicates and sort
        unique_entries = {}
        for ep in entry_points:
            ep_name = ep["name"]
            if ep_name not in unique_entries or ep["callees"] > unique_entries[ep_name]["callees"]:
                unique_entries[ep_name] = ep
        
        return sorted(unique_entries.values(), key=lambda x: (x["callers"], -x["callees"]))[:20]
    
    def get_exit_points(self) -> List[Dict]:
        """
        Identify exit points (terminal functions that don't call others).
        Uses call graph directly as primary source, falls back to symbol table.
        """
        exit_points = []
        added_names = set()
        
        # Strategy 1: Use call graph - functions that are called but don't call others
        if self.call_graph:
            all_callers = set(self.call_graph.keys())
            all_callees = set()
            in_degree = defaultdict(int)
            
            for caller, callees in self.call_graph.items():
                callees_list = callees if isinstance(callees, list) else (list(callees.values()) if isinstance(callees, dict) else [])
                for callee in callees_list:
                    all_callees.add(callee)
                    in_degree[callee] += 1
            
            # Exit points: called by others (in_degree > 0) but don't call anything
            for func_name in all_callees:
                if func_name not in all_callers:
                    # This function is called but doesn't call anything (exit point)
                    name_parts = func_name.split(':')
                    short_name = name_parts[-1] if name_parts else func_name
                    start_line, end_line = self._lookup_line_info(short_name)
                    
                    exit_points.append({
                        "name": func_name,
                        "file": name_parts[0] + ':' + name_parts[1] if len(name_parts) > 1 else 'unknown',
                        "type": "function",
                        "start_line": start_line,
                        "end_line": end_line,
                        "callers": in_degree[func_name],
                    })
                    added_names.add(func_name)
        
        # Strategy 2: Also look at functions that DO exist in call graph but with zero callees
        if self.call_graph:
            in_degree = defaultdict(int)
            for caller, callees in self.call_graph.items():
                callees_list = callees if isinstance(callees, list) else (list(callees.values()) if isinstance(callees, dict) else [])
                for callee in callees_list:
                    in_degree[callee] += 1
            
            for func_name, callees in self.call_graph.items():
                if func_name not in added_names:
                    callees_list = callees if isinstance(callees, list) else (list(callees.values()) if isinstance(callees, dict) else [])
                    if not callees_list and in_degree[func_name] > 0:
                        # Called by others but makes no calls
                        name_parts = func_name.split(':')
                        short_name = name_parts[-1] if name_parts else func_name
                        start_line, end_line = self._lookup_line_info(short_name)
                        
                        exit_points.append({
                            "name": func_name,
                            "file": name_parts[0] + ':' + name_parts[1] if len(name_parts) > 1 else 'unknown',
                            "type": "function",
                            "start_line": start_line,
                            "end_line": end_line,
                            "callers": in_degree[func_name],
                        })
                        added_names.add(func_name)
        
        # Remove duplicates and sort by caller count
        unique_exits = {}
        for ep in exit_points:
            ep_name = ep["name"]
            if ep_name not in unique_exits or ep["callers"] > unique_exits[ep_name]["callers"]:
                unique_exits[ep_name] = ep
        
        return sorted(unique_exits.values(), key=lambda x: -x["callers"])[:20]
    
    def get_dependency_order(self) -> List[Dict]:
        """
        Generate ordered list of files/functions for onboarding.
        Uses multi-source ordering:
        1. Topological sort of call graph (dependency depth from entry points)
        2. Knowledge graph semantic relationships
        3. Dataflow dependencies (reads/writes)
        4. Complexity metrics
        """
        # Build reverse graph
        reverse_graph = defaultdict(set)
        for caller, callees in self.call_graph.items():
            for callee in callees:
                reverse_graph[callee].add(caller)
        
        # BFS from entry points to determine depth
        entry_points = self.get_entry_points()
        visited = set()
        depth_map = {}
        queue = deque()
        
        # Start from identified entry points
        for ep in entry_points:
            ep_name = ep["name"]
            queue.append((ep_name, 0))
            depth_map[ep_name] = 0
        
        while queue:
            current, depth = queue.popleft()
            
            if current in visited:
                continue
            visited.add(current)
            
            if current in self.call_graph:
                for callee in self.call_graph[current]:
                    if callee not in depth_map or depth_map[callee] > depth + 1:
                        depth_map[callee] = depth + 1
                        queue.append((callee, depth + 1))
            
            # Also traverse dataflow dependencies
            if current in self.dataflow_relationships:
                deps = self.dataflow_relationships[current].get("depends_on", [])
                for dep in deps:
                    if dep not in depth_map or depth_map[dep] > depth + 0.5:
                        depth_map[dep] = depth + 0.5
                        queue.append((dep, depth + 0.5))
        
        # Group by file and compute complexity metrics
        roadmap = []
        file_depths = defaultdict(list)
        
        for symbol_name, symbol_info in self.symbol_table.items():
            if isinstance(symbol_info, dict):
                file_path = symbol_info.get("file", "unknown")
                depth = depth_map.get(symbol_name, float('inf'))
                
                # Compute complexity score from dataflow analysis
                complexity_score = 0
                if symbol_name in self.dataflow_relationships:
                    df_info = self.dataflow_relationships[symbol_name]
                    complexity_score = len(df_info.get("reads", [])) + len(df_info.get("writes", [])) * 2
                
                file_depths[file_path].append({
                    "name": symbol_name,
                    "type": symbol_info.get("type", "unknown"),
                    "depth": depth,
                    "start_line": symbol_info.get("start_line", 0),
                    "end_line": symbol_info.get("end_line", 0),
                    "complexity": complexity_score,
                })
        
        # Sort files by minimum depth, then symbols by depth + complexity
        for file_path in sorted(file_depths.keys(), 
                               key=lambda x: min((item["depth"] for item in file_depths[x] if item["depth"] != float('inf')), default=float('inf'))):
            symbols = sorted(file_depths[file_path], key=lambda x: (x["depth"], -x["complexity"]))
            roadmap.append({
                "file": file_path,
                "symbols": symbols,
                "min_depth": min((item["depth"] for item in symbols if item["depth"] != float('inf')), default=float('inf')),
            })
        
        return roadmap
    
    def get_file_tree(self) -> Dict:
        """Build file structure tree from repository."""
        tree = {"name": "root", "type": "folder", "children": []}
        file_structure = {"files": [], "folders": {}}
        
        # Collect all files from symbol table first, then vectorstore
        all_files = set()
        for symbol_info in self.symbol_table.values():
            if isinstance(symbol_info, dict):
                file_path = symbol_info.get("file", "")
                if file_path:
                    all_files.add(file_path)
        
        # Also add files from vectorstore if available
        if self.vectorstore_files:
            all_files.update(self.vectorstore_files)
        
        if not all_files:
            # Fallback: try to infer from call graph keys
            for symbol_name in self.call_graph.keys():
                if isinstance(self.symbol_table.get(symbol_name), dict):
                    file_path = self.symbol_table[symbol_name].get("file", "")
                    if file_path:
                        all_files.add(file_path)
        
        # Build tree structure
        for file_path in sorted(all_files):
            parts = file_path.replace("\\", "/").split("/")
            current = file_structure
            
            for part in parts[:-1]:
                if part not in current["folders"]:
                    current["folders"][part] = {"files": [], "folders": {}}
                current = current["folders"][part]
            
            current["files"].append(parts[-1] if parts else file_path)
        
        def dict_to_tree(d, name="root"):
            node = {"name": name, "type": "folder", "children": []}
            
            for folder_name, folder_content in sorted(d["folders"].items()):
                node["children"].append(dict_to_tree(folder_content, folder_name))
            
            for file_name in sorted(d["files"]):
                node["children"].append({"name": file_name, "type": "file"})
            
            return node
        
        return dict_to_tree(file_structure)
    
    def get_related_symbols(self, symbol_name: str) -> Dict:
        """Get callers, callees, and related symbols for a given symbol."""
        callers = []
        callees = []
        
        # Find callers (symbols that call this one)
        for caller, called_set in self.call_graph.items():
            if symbol_name in called_set:
                callers.append(caller)
        
        # Find callees (symbols called by this one)
        if symbol_name in self.call_graph:
            callees = list(self.call_graph[symbol_name])
        
        return {
            "symbol": symbol_name,
            "callers": sorted(callers),
            "callees": sorted(callees),
            "num_callers": len(callers),
            "num_callees": len(callees),
        }
    
    def get_files_with_weak_docs(self) -> List[Dict]:
        """
        Detect functions/methods with missing or weak documentation.
        Functions with weak docs have:
        - No docstring or very short docstring  
        - Complex logic (many lines, many calls, high dataflow)
        Uses complexity heuristics since symbol table may not have docstring info.
        """
        weak_doc_symbols = []
        
        # Extract docstring presence from vectorstore if available
        docs_with_docstrings = set()
        if self.vectorstore:
            try:
                all_docs = list(self.vectorstore.docstore._dict.values())
                for doc in all_docs:
                    metadata = doc.metadata
                    # If vectorstore has extracted docstrings, track them
                    if metadata.get("has_docstring"):
                        docs_with_docstrings.add(metadata.get("name", ""))
            except Exception as e:
                pass  # Silently fail - vectorstore may not have this info
        
        # Build a mapping of short names to full call graph names
        short_name_to_cg = {}
        for cg_name in self.call_graph.keys():
            short_name = cg_name.split(':')[-1]  # Extract last part
            short_name_to_cg[short_name] = cg_name
        
        for symbol_name, symbol_info in self.symbol_table.items():
            if isinstance(symbol_info, dict):
                kind = symbol_info.get("kind", "unknown")
                
                # Focus on functions and methods
                if kind not in ["function", "method"]:
                    continue
                
                # Get complexity metrics
                start_line = symbol_info.get("start_line", 0)
                end_line = symbol_info.get("end_line", 0)
                lines = max(1, end_line - start_line)
                
                # Find corresponding call graph entry
                cg_name = short_name_to_cg.get(symbol_name, symbol_name)
                
                # Count callees (function calls it makes)
                num_callees = len(self.call_graph.get(cg_name, []))
                
                # Count callers (how many times it's called)
                in_degree = 0
                for callees in self.call_graph.values():
                    callees_list = callees if isinstance(callees, list) else (list(callees.values()) if isinstance(callees, dict) else [])
                    if cg_name in callees_list:
                        in_degree += 1
                
                # Dataflow complexity (if available)
                dataflow_complexity = 0
                if symbol_name in self.dataflow_relationships:
                    df = self.dataflow_relationships[symbol_name]
                    dataflow_complexity = len(df.get("reads", [])) + len(df.get("writes", []))
                
                # Check if has docstring (heuristic or from vectorstore)
                has_doc = symbol_name in docs_with_docstrings
                doc_length = len(symbol_info.get("docstring", "").strip()) if "docstring" in symbol_info else 0
                
                # Complexity score: lines + calls + dataflow
                complexity_score = lines + (num_callees * 5) + (dataflow_complexity * 3) + (in_degree * 2)
                
                # Weak if: no/short doc AND (complex OR calls many functions OR called frequently)
                is_weak = (not has_doc and doc_length < 30) and (
                    complexity_score > 15 or  # Generally complex
                    num_callees >= 3 or       # Calls many functions
                    in_degree >= 2            # Called by multiple places
                )
                
                if is_weak:
                    weak_doc_symbols.append({
                        "name": symbol_name,
                        "file": symbol_info.get("file", "unknown"),
                        "type": kind,
                        "lines": lines,
                        "callees": num_callees,
                        "callers": in_degree,
                        "dataflow_ops": dataflow_complexity,
                        "doc_length": doc_length,
                        "complexity_score": complexity_score,
                        "start_line": start_line,
                        "end_line": end_line,
                    })
        
        # Return sorted by complexity (most complex/important first)
        return sorted(weak_doc_symbols, key=lambda x: -x["complexity_score"])
    
    def generate_project_summary(self, context: str = "", llm=None) -> str:
        """
        Generate a brief project summary using available metadata.
        If LLM is provided, use it to enhance the summary.
        """
        stats = self.get_project_stats()
        entry_points = self.get_entry_points()
        
        summary = f"""
# Project Overview

**Statistics:**
- Total Files: {stats['total_files']}
- Total Functions: {stats['total_functions']}
- Total Classes: {stats['total_classes']}

**Entry Points:**
{chr(10).join(f"- {ep['name']} ({ep['file']})" for ep in entry_points[:5])}

**Primary Technologies:**
Based on file structure and function patterns, this project appears to be a Python-based application.
"""
        
        if llm and context:
            try:
                enhanced = llm.invoke(f"""
Based on this codebase metadata, generate a 2-3 sentence project summary:

{summary}

Context: {context[:500]}

Generate a concise, professional summary that a new developer would understand.
""").content
                return enhanced
            except Exception as e:
                print(f"⚠️ LLM summary generation failed: {e}")
                return summary
        
        return summary
