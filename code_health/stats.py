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
        """Compute statistics for each source file (multi-language support)."""
        file_stats = {}
        
        # Supported file extensions across all languages
        supported_extensions = {
            '.py': 'python',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.go': 'go',
            '.rs': 'rust',
        }
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip common non-essential directories
            dirs[:] = [d for d in dirs if d not in [
                '__pycache__', '.git', '.venv', 'venv', 'node_modules', '.pytest_cache',
                'target', 'build', 'dist', '.gradle', '.idea', 'vendor'
            ]]
            
            for file in files:
                file_ext = os.path.splitext(file)[1]
                if file_ext in supported_extensions:
                    file_path = os.path.join(root, file)
                    language = supported_extensions[file_ext]
                    try:
                        stats = self._analyze_file(file_path, language)
                        # Use relative path as key
                        rel_path = os.path.relpath(file_path, self.repo_path)
                        file_stats[rel_path] = stats
                    except Exception as e:
                        print(f"⚠️ Error analyzing {file_path}: {e}")
        
        return file_stats
    
    def _analyze_file(self, file_path: str, language: str) -> Dict:
        """Analyze a single source file (multi-language support)."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Basic structure that works for all languages
        stats = {
            'path': file_path,
            'language': language,
            'loc': len(lines),
            'loc_code': self._count_code_lines(lines, language),
            'loc_blank': self._count_blank_lines(lines),
            'loc_comment': self._count_comment_lines(lines, language),
            'num_functions': self._count_functions(content, file_path, language),
            'num_classes': self._count_classes(content, file_path, language),
            'num_imports': self._count_imports(content, language),
            'cyclomatic_complexity': self._estimate_complexity(content, language),
            'average_function_length': self._compute_average_function_length(content, language),
            'has_docstring': self._has_module_docstring(content, language),
            'docstring_coverage': self._compute_docstring_coverage(content, file_path, language),
            'fan_in': self._compute_fan_in(file_path),
            'fan_out': self._compute_fan_out(file_path, language),
            'dependency_count': self._count_imports(content, language),
        }
        
        # Compute comment-to-code ratio
        stats['comment_to_code_ratio'] = (
            stats['loc_comment'] / max(stats['loc_code'], 1)
        )
        
        return stats
    
    def _count_code_lines(self, lines: List[str], language: str = 'python') -> int:
        """Count non-blank, non-comment lines (language-aware)."""
        count = 0
        
        if language == 'python':
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    count += 1
        elif language in ('java', 'c', 'cpp', 'javascript', 'typescript', 'go', 'rust'):
            # For C-style languages, ignore //, /* and *lines
            in_multiline = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                
                # Track multiline comments
                if '/*' in stripped:
                    in_multiline = True
                if '*/' in stripped:
                    in_multiline = False
                    continue
                
                if in_multiline:
                    continue
                
                # Skip if line is only a comment
                if not (stripped.startswith('//') or stripped.startswith('*')):
                    count += 1
        else:
            # Fallback: count any non-blank line
            count = sum(1 for line in lines if line.strip())
        
        return count
    
    def _count_blank_lines(self, lines: List[str]) -> int:
        """Count blank lines."""
        return sum(1 for line in lines if line.strip() == '')
    
    def _count_comment_lines(self, lines: List[str], language: str = 'python') -> int:
        """Count comment-only lines (language-aware)."""
        count = 0
        in_multiline_comment = False
        
        if language == 'python':
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
        else:
            # C-style languages: //, /*, */
            for line in lines:
                stripped = line.strip()
                
                if '/*' in stripped:
                    in_multiline_comment = True
                    count += 1
                    continue
                
                if '*/' in stripped:
                    in_multiline_comment = False
                    count += 1
                    continue
                
                if in_multiline_comment:
                    count += 1
                elif stripped.startswith('//') or stripped.startswith('*'):
                    count += 1
        
        return count
    
    def _count_functions(self, content: str, file_path: str, language: str) -> int:
        """Count function/method definitions (language-aware, with symbol_table fallback)."""
        # Try to use symbol_table if available
        try:
            rel_path = os.path.relpath(file_path, self.repo_path)
            if rel_path in self.symbol_table:
                symbols = self.symbol_table.get(rel_path, {}).get('symbols', {})
                return sum(1 for s in symbols.values() if s.get('kind') in ('function', 'method'))
        except Exception:
            pass
        
        # Fallback to regex parsing by language
        if language == 'python':
            return len(re.findall(r'^\s*def\s+\w+\s*\(', content, re.MULTILINE))
        elif language == 'java':
            return len(re.findall(r'^\s*(?:public|private|protected|static)?\s*(?:void|int|String|boolean|.*?)\s+\w+\s*\(', content, re.MULTILINE))
        elif language in ('cpp', 'c'):
            return len(re.findall(r'^\s*(?:static|inline|virtual)?\s*\w+\s+\w+\s*\([^)]*\)\s*(?:{|;)', content, re.MULTILINE))
        elif language in ('javascript', 'typescript'):
            return len(re.findall(r'^\s*(?:async\s+)?(?:function\s+\w+|(?:\w+\s*:\s*)?function\s*\()', content, re.MULTILINE)) + \
                   len(re.findall(r'^\s*\w+\s*=\s*(?:async\s+)?\(', content, re.MULTILINE))
        elif language == 'go':
            return len(re.findall(r'^\s*func\s+\(.*?\)\s+\w+\s*\(|^\s*func\s+\w+\s*\(', content, re.MULTILINE))
        elif language == 'rust':
            return len(re.findall(r'^\s*(?:pub\s+)?(?:async\s+)?fn\s+\w+\s*\(', content, re.MULTILINE))
        
        return 0
    
    def _count_classes(self, content: str, file_path: str, language: str) -> int:
        """Count class/struct/interface definitions (language-aware, with symbol_table fallback)."""
        # Try to use symbol_table if available
        try:
            rel_path = os.path.relpath(file_path, self.repo_path)
            if rel_path in self.symbol_table:
                symbols = self.symbol_table.get(rel_path, {}).get('symbols', {})
                return sum(1 for s in symbols.values() if s.get('kind') == 'class')
        except Exception:
            pass
        
        # Fallback to regex parsing by language
        if language == 'python':
            return len(re.findall(r'^\s*class\s+\w+', content, re.MULTILINE))
        elif language == 'java':
            return len(re.findall(r'^\s*(?:public|private)?\s*(?:abstract)?\s*class\s+\w+|^\s*interface\s+\w+', content, re.MULTILINE))
        elif language in ('cpp', 'c'):
            return len(re.findall(r'^\s*(?:struct|class|union)\s+\w+\s*{', content, re.MULTILINE))
        elif language in ('javascript', 'typescript'):
            return len(re.findall(r'^\s*(?:export\s+)?class\s+\w+', content, re.MULTILINE))
        elif language == 'go':
            return len(re.findall(r'^\s*type\s+\w+\s+struct', content, re.MULTILINE))
        elif language == 'rust':
            return len(re.findall(r'^\s*(?:pub\s+)?(?:struct|impl|trait)\s+\w+', content, re.MULTILINE))
        
        return 0
    
    def _count_imports(self, content: str, language: str) -> int:
        """Count import statements (language-aware)."""
        if language == 'python':
            return len(re.findall(r'^\s*(?:import|from)\s+', content, re.MULTILINE))
        elif language == 'java':
            return len(re.findall(r'^\s*import\s+[\w.]+;', content, re.MULTILINE))
        elif language in ('cpp', 'c'):
            return len(re.findall(r'^\s*#include\s+[<"]', content, re.MULTILINE))
        elif language in ('javascript', 'typescript'):
            return len(re.findall(r'^\s*(?:import|require)\s+', content, re.MULTILINE))
        elif language == 'go':
            return len(re.findall(r'^\s*import\s+[\w"./]', content, re.MULTILINE))
        elif language == 'rust':
            return len(re.findall(r'^\s*use\s+[\w:]+', content, re.MULTILINE))
        
        return 0
    
    def _estimate_complexity(self, content: str, language: str) -> float:
        """
        Estimate cyclomatic complexity (language-aware).
        CC = 1 + sum of decision points (if, else, loops, case, etc.)
        """
        cc = 1  # Base complexity
        
        if language == 'python':
            decision_keywords = [r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
                                r'\bexcept\b', r'\bfinally\b', r'\band\b', r'\bor\b', r'\bwith\b']
        elif language == 'java':
            decision_keywords = [r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bswitch\b',
                                r'\bcase\b', r'\bcatch\b', r'\bfinally\b', r'&&', r'\|\|', r'\?']
        elif language in ('cpp', 'c'):
            decision_keywords = [r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bdo\b',
                                r'\bswitch\b', r'\bcase\b', r'&&', r'\|\|', r'\?']
        elif language in ('javascript', 'typescript'):
            decision_keywords = [r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bswitch\b',
                                r'\bcase\b', r'\bcatch\b', r'&&', r'\|\|', r'\?']
        elif language == 'go':
            decision_keywords = [r'\bif\b', r'\belse\b', r'\bfor\b', r'\bswitch\b', r'\bcase\b',
                                r'\bdefault\b', r'&&', r'\|\|']
        elif language == 'rust':
            decision_keywords = [r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bmatch\b',
                                r'\b_\b', r'&&', r'\|\|']
        else:
            decision_keywords = []
        
        for keyword in decision_keywords:
            try:
                count = len(re.findall(keyword, content))
                cc += count
            except:
                pass
        
        return max(cc, 1)
    
    def _compute_average_function_length(self, content: str, language: str) -> float:
        """Compute average function length in lines (language-aware)."""
        func_pattern = None
        
        if language == 'python':
            func_pattern = r'def\s+\w+\s*\([^)]*\):[^\n]*\n((?:\n|.)*?)(?=\ndef\s|\nclass\s|\Z)'
        elif language == 'java':
            func_pattern = r'(?:public|private|protected)?\s*(?:\w+\s+)*\w+\s*\([^)]*\)\s*{((?:[^{}]|{[^}]*})*?)}'
        elif language in ('cpp', 'c'):
            func_pattern = r'\w+\s+\w+\s*\([^)]*\)\s*{((?:[^{}]|{[^}]*})*?)}'
        elif language in ('javascript', 'typescript'):
            func_pattern = r'(?:function\s+\w+|async?\s+\w+)\s*\([^)]*\)\s*{((?:[^{}]|{[^}]*})*?)}'
        else:
            return 0
        
        try:
            functions = re.findall(func_pattern, content, re.MULTILINE)
            if not functions:
                return 0
            
            total_lines = sum(len(func.split('\n')) for func in functions)
            return total_lines / len(functions)
        except:
            return 0
    
    def _has_module_docstring(self, content: str, language: str) -> bool:
        """Check if file has a module-level docstring/comment."""
        if language == 'python':
            return bool(re.search(r'^\s*("""|\'\'\').*?("""|\'\'\')' , content, re.MULTILINE))
        elif language == 'java':
            return bool(re.search(r'^\s*/\*\*[\s\S]*?\*/', content, re.MULTILINE))
        elif language in ('cpp', 'c'):
            return bool(re.search(r'^\s*/\*[\s\S]*?\*/', content, re.MULTILINE))
        elif language in ('javascript', 'typescript'):
            return bool(re.search(r'^\s*(//|/\*)', content, re.MULTILINE))
        else:
            return False
    
    def _compute_docstring_coverage(self, content: str, file_path: str, language: str) -> float:
        """Compute percentage of functions/methods with docstrings (language-aware)."""
        try:
            total_funcs = self._count_functions(content, file_path, language)
            if total_funcs == 0:
                return 0
            
            documented = 0
            
            if language == 'python':
                # Functions with docstrings
                documented = len(re.findall(
                    r'def\s+\w+\s*\([^)]*\):\s*\n\s*("""|\'\'\').*?("""|\'\'\')',
                    content, re.MULTILINE | re.DOTALL
                ))
            elif language == 'java':
                # Methods with Javadoc
                documented = len(re.findall(
                    r'/\*\*[\s\S]*?\*/\s*(?:public|private|protected)?\s*(?:\w+\s+)*\w+\s*\(',
                    content
                ))
            elif language in ('cpp', 'c'):
                # Functions with comments/documentation
                documented = len(re.findall(
                    r'/\*[\s\S]*?\*/\s*\w+\s+\w+\s*\([^)]*\)',
                    content
                ))
            elif language in ('javascript', 'typescript'):
                # Functions with JSDoc comments
                documented = len(re.findall(
                    r'/\*\*[\s\S]*?\*/\s*(?:async\s+)?(?:function\s+\w+|\w+\s*=\s*\()',
                    content
                ))
            
            return (documented / total_funcs) * 100
        except:
            return 0
    
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
    
    def _compute_fan_out(self, file_path: str, language: str) -> int:
        """Compute fan-out: number of files this file depends on (language-aware)."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if language == 'python':
                imports = re.findall(r'^\s*(?:import|from)\s+([\w.]+)', content, re.MULTILINE)
                # Count only internal imports
                internal_imports = 0
                for imp in imports:
                    if not imp.startswith(('sys', 'os', 'json', 're', 'collections', 'typing', 'pathlib', 'ast')):
                        internal_imports += 1
                return internal_imports
            
            elif language == 'java':
                imports = re.findall(r'^\s*import\s+([\w.]+);', content, re.MULTILINE)
                # Exclude java.* imports
                internal_imports = sum(1 for i in imports if not i.startswith('java.'))
                return internal_imports
            
            elif language in ('cpp', 'c'):
                imports = re.findall(r'^\s*#include\s+["]([^"]+)["]', content, re.MULTILINE)
                # Local includes count as dependencies
                return len(imports)
            
            elif language in ('javascript', 'typescript'):
                imports = re.findall(r'^\s*import\s+.*?from\s+["\']([^"\']+)["\']', content, re.MULTILINE)
                # Count only non-node_modules imports
                internal_imports = sum(1 for i in imports if not i.startswith(('react', 'lodash', 'express')))
                return internal_imports
            
            elif language == 'go':
                imports = re.findall(r'^\s*import\s+["`][^`"]+["`]', content, re.MULTILINE)
                return len(imports)
            
            elif language == 'rust':
                imports = re.findall(r'^\s*use\s+[\w:]+', content, re.MULTILINE)
                internal_imports = sum(1 for i in imports if not i.startswith('std::'))
                return internal_imports
            
            return 0
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
