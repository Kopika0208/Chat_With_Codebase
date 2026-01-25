"""
Static code statistics computation.
Computes LOC, function/class counts, complexity, churn, and dependency metrics.
"""

import os
import re
import json
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import subprocess
from pathlib import Path


class CodeStatistics:
    """Computes comprehensive code statistics."""
    
    def __init__(self, repo_path: str, call_graph: Dict, symbol_table: Dict):
        """
        Initialize statistics computer.
        
        Args:
            repo_path: Path to repository source files
            call_graph: Call graph data structure
            symbol_table: Symbol table with function/class metadata
        """
        self.repo_path = repo_path
        # Ensure call_graph is always a dict
        self.call_graph = call_graph if isinstance(call_graph, dict) else {}
        # Ensure symbol_table is always a dict
        self.symbol_table = symbol_table if isinstance(symbol_table, dict) else {}
        self.file_stats = {}
        self.module_stats = {}
        self.repo_stats = {}
    
    def compute_all_statistics(self) -> Dict:
        """Compute all code statistics."""
        # File-level statistics
        self.file_stats = self._compute_file_statistics()
        
        # Module-level aggregation
        self.module_stats = self._compute_module_statistics()
        
        # Repository-level aggregation
        self.repo_stats = self._compute_repository_statistics()
        
        return {
            "file_stats": self.file_stats,
            "module_stats": self.module_stats,
            "repo_stats": self.repo_stats,
        }
    
    def _compute_file_statistics(self) -> Dict:
        """Compute statistics for each Python file."""
        file_stats = {}
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip common non-essential directories
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', '.venv', 'venv', 'node_modules', '.pytest_cache'
            ]]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        stats = self._analyze_python_file(file_path)
                        # Use relative path as key
                        rel_path = os.path.relpath(file_path, self.repo_path)
                        file_stats[rel_path] = stats
                    except Exception as e:
                        print(f"⚠️ Error analyzing {file_path}: {e}")
        
        return file_stats
    
    def _analyze_python_file(self, file_path: str) -> Dict:
        """Analyze a single Python file."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        stats = {
            'path': file_path,
            'loc': len(lines),
            'loc_code': self._count_code_lines(lines),
            'loc_blank': self._count_blank_lines(lines),
            'loc_comment': self._count_comment_lines(lines),
            'num_functions': len(re.findall(r'^\s*def\s+\w+\s*\(', content, re.MULTILINE)),
            'num_classes': len(re.findall(r'^\s*class\s+\w+', content, re.MULTILINE)),
            'num_imports': len(re.findall(r'^\s*(import|from)\s+', content, re.MULTILINE)),
            'cyclomatic_complexity': self._compute_cyclomatic_complexity(content),
            'average_function_length': self._compute_average_function_length(content),
            'has_docstring': self._has_module_docstring(content),
            'docstring_coverage': self._compute_docstring_coverage(content),
            'fan_in': self._compute_fan_in(file_path),
            'fan_out': self._compute_fan_out(file_path),
            'dependency_count': len(re.findall(r'^\s*(import|from)\s+', content, re.MULTILINE)),
        }
        
        # Compute comment-to-code ratio
        stats['comment_to_code_ratio'] = (
            stats['loc_comment'] / max(stats['loc_code'], 1)
        )
        
        return stats
    
    def _count_code_lines(self, lines: List[str]) -> int:
        """Count non-blank, non-comment lines."""
        count = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                count += 1
        return count
    
    def _count_blank_lines(self, lines: List[str]) -> int:
        """Count blank lines."""
        return sum(1 for line in lines if line.strip() == '')
    
    def _count_comment_lines(self, lines: List[str]) -> int:
        """Count comment-only lines."""
        count = 0
        in_multiline_comment = False
        for line in lines:
            stripped = line.strip()
            
            # Track triple-quoted strings (docstrings/comments)
            if '"""' in stripped or "'''" in stripped:
                in_multiline_comment = not in_multiline_comment
                count += 1
            elif in_multiline_comment:
                count += 1
            elif stripped.startswith('#') and stripped:
                count += 1
        
        return count
    
    def _compute_cyclomatic_complexity(self, content: str) -> float:
        """
        Compute cyclomatic complexity using decision points.
        CC = 1 + sum of decision points (if, elif, except, for, while, and, or, etc.)
        """
        cc = 1  # Base complexity
        
        # Count decision points
        decision_keywords = [
            r'\bif\b', r'\belif\b', r'\belse\b',
            r'\bfor\b', r'\bwhile\b',
            r'\bexcept\b', r'\bfinally\b',
            r'\band\b', r'\bor\b',
            r'\bwith\b'
        ]
        
        for keyword in decision_keywords:
            count = len(re.findall(keyword, content))
            cc += count
        
        return max(cc, 1)  # At least 1
    
    def _compute_average_function_length(self, content: str) -> float:
        """Compute average function length in lines."""
        # Extract function bodies (simplified)
        functions = re.findall(r'def\s+\w+\s*\([^)]*\):[^\n]*\n((?:\n|.)*?)(?=\ndef\s|\nclass\s|\Z)', content)
        
        if not functions:
            return 0
        
        total_lines = sum(len(func.split('\n')) for func in functions)
        return total_lines / len(functions)
    
    def _has_module_docstring(self, content: str) -> bool:
        """Check if file has a module-level docstring."""
        return bool(re.search(r'^\s*("""|\'\'\').*?("""|\'\'\')' , content, re.MULTILINE))
    
    def _compute_docstring_coverage(self, content: str) -> float:
        """Compute percentage of functions with docstrings."""
        functions = len(re.findall(r'^\s*def\s+\w+\s*\(', content, re.MULTILINE))
        
        if functions == 0:
            return 0
        
        # Count functions with docstrings (simplified)
        documented = len(re.findall(
            r'def\s+\w+\s*\([^)]*\):\s*\n\s*("""|\'\'\').*?("""|\'\'\')',
            content,
            re.MULTILINE | re.DOTALL
        ))
        
        return (documented / functions) * 100
    
    def _compute_fan_in(self, file_path: str) -> int:
        """Compute fan-in: number of files that depend on this file."""
        rel_path = os.path.relpath(file_path, self.repo_path)
        
        # Count how many other files import from this file
        fan_in = 0
        module_name = rel_path.replace(os.sep, '.').replace('.py', '')
        
        for other_path, other_stats in self.file_stats.items():
            if other_path == rel_path:
                continue
            
            # This is a simplified check - would need import parsing for accuracy
            fan_in += 1 if module_name in str(other_stats) else 0
        
        return fan_in
    
    def _compute_fan_out(self, file_path: str) -> int:
        """Compute fan-out: number of files this file depends on."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            imports = re.findall(r'^\s*(?:import|from)\s+([\w.]+)', content, re.MULTILINE)
            
            # Count only internal imports (simplified)
            internal_imports = 0
            for imp in imports:
                if not imp.startswith(('sys', 'os', 'json', 're', 'collections', 'typing', 'pathlib')):
                    internal_imports += 1
            
            return internal_imports
        except:
            return 0
    
    def _compute_module_statistics(self) -> Dict:
        """Aggregate file statistics by module."""
        module_stats = defaultdict(lambda: {
            'num_files': 0,
            'loc': 0,
            'loc_code': 0,
            'num_functions': 0,
            'num_classes': 0,
            'avg_cyclomatic_complexity': 0,
            'avg_function_length': 0,
        })
        
        for file_path, stats in self.file_stats.items():
            module = file_path.split(os.sep)[0] if os.sep in file_path else 'root'
            
            module_stats[module]['num_files'] += 1
            module_stats[module]['loc'] += stats['loc']
            module_stats[module]['loc_code'] += stats['loc_code']
            module_stats[module]['num_functions'] += stats['num_functions']
            module_stats[module]['num_classes'] += stats['num_classes']
            module_stats[module]['avg_cyclomatic_complexity'] += stats['cyclomatic_complexity']
            module_stats[module]['avg_function_length'] += stats['average_function_length']
        
        # Compute averages
        for module in module_stats:
            num_files = module_stats[module]['num_files']
            if num_files > 0:
                module_stats[module]['avg_cyclomatic_complexity'] /= num_files
                module_stats[module]['avg_function_length'] /= num_files
        
        return dict(module_stats)
    
    def _compute_repository_statistics(self) -> Dict:
        """Compute repository-wide statistics."""
        if not self.file_stats:
            return {}
        
        total_loc = sum(s['loc'] for s in self.file_stats.values())
        total_loc_code = sum(s['loc_code'] for s in self.file_stats.values())
        total_loc_comment = sum(s['loc_comment'] for s in self.file_stats.values())
        total_functions = sum(s['num_functions'] for s in self.file_stats.values())
        total_classes = sum(s['num_classes'] for s in self.file_stats.values())
        total_complexity = sum(s['cyclomatic_complexity'] for s in self.file_stats.values())
        
        avg_function_length = (
            sum(s['average_function_length'] * s['num_functions'] 
                for s in self.file_stats.values() if s['num_functions'] > 0)
            / max(total_functions, 1)
        )
        
        return {
            'num_files': len(self.file_stats),
            'total_loc': total_loc,
            'total_loc_code': total_loc_code,
            'total_loc_comment': total_loc_comment,
            'loc_blank': sum(s['loc_blank'] for s in self.file_stats.values()),
            'num_functions': total_functions,
            'num_classes': total_classes,
            'avg_function_length': avg_function_length,
            'avg_class_size': total_loc / max(total_classes, 1),
            'comment_to_code_ratio': total_loc_comment / max(total_loc_code, 1),
            'avg_cyclomatic_complexity': total_complexity / max(len(self.file_stats), 1),
            'num_modules': len(self.module_stats),
        }
    
    def get_high_complexity_functions(self, threshold: float = 10) -> List[Dict]:
        """Get functions with high cyclomatic complexity."""
        high_complexity = []
        
        for file_path, stats in self.file_stats.items():
            if stats['cyclomatic_complexity'] > threshold:
                high_complexity.append({
                    'file': file_path,
                    'complexity': stats['cyclomatic_complexity'],
                    'loc': stats['loc'],
                })
        
        return sorted(high_complexity, key=lambda x: x['complexity'], reverse=True)
    
    def get_large_files(self, threshold: int = 500) -> List[Dict]:
        """Get files exceeding LOC threshold."""
        large_files = []
        
        for file_path, stats in self.file_stats.items():
            if stats['loc'] > threshold:
                large_files.append({
                    'file': file_path,
                    'loc': stats['loc'],
                    'num_functions': stats['num_functions'],
                    'num_classes': stats['num_classes'],
                })
        
        return sorted(large_files, key=lambda x: x['loc'], reverse=True)
    
    def get_poorly_documented_files(self, threshold: float = 10) -> List[Dict]:
        """Get files with low docstring coverage."""
        poorly_documented = []
        
        for file_path, stats in self.file_stats.items():
            if stats['docstring_coverage'] < threshold and stats['num_functions'] > 0:
                poorly_documented.append({
                    'file': file_path,
                    'docstring_coverage': stats['docstring_coverage'],
                    'num_functions': stats['num_functions'],
                })
        
        return sorted(poorly_documented, key=lambda x: x['docstring_coverage'])
