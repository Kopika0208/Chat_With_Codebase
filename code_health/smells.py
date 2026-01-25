"""
Code Smell Detection.
Identifies common code smells using heuristics and metrics.
"""

from typing import Dict, List
import re


class CodeSmellDetector:
    """Detects common code smells."""
    
    def __init__(self, stats: Dict, call_graph: Dict, symbol_table: Dict, repo_path: str):
        """
        Initialize smell detector.
        
        Args:
            stats: Code statistics
            call_graph: Call graph data
            symbol_table: Symbol table data
            repo_path: Path to repository
        """
        self.stats = stats if isinstance(stats, dict) else {}
        self.call_graph = call_graph if isinstance(call_graph, dict) else {}
        self.symbol_table = symbol_table if isinstance(symbol_table, dict) else {}
        self.repo_path = repo_path
        self.detected_smells = []
    
    def detect_all_smells(self) -> List[Dict]:
        """Detect all code smells."""
        self.detected_smells = []
        
        self._detect_god_files()
        self._detect_long_functions()
        self._detect_high_complexity()
        self._detect_tight_coupling()
        self._detect_unused_code()
        self._detect_orphaned_files()
        self._detect_hotspots()
        
        return self.detected_smells
    
    def _detect_god_files(self):
        """Detect god files (too large, too many responsibilities)."""
        repo_stats = self.stats.get('repo_stats', {})
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return
        
        num_files = repo_stats.get('num_files', 1)
        avg_loc = repo_stats.get('total_loc', 0) / max(num_files, 1)
        god_threshold = avg_loc * 3
        
        for file_path, stats in file_stats.items():
            if stats['loc'] > god_threshold:
                self.detected_smells.append({
                    'type': 'God File',
                    'file': file_path,
                    'severity': 'high' if stats['loc'] > god_threshold * 2 else 'medium',
                    'description': f"File is too large ({stats['loc']} LOC, avg: {int(avg_loc)} LOC). "
                                 f"Contains {stats['num_functions']} functions and {stats['num_classes']} classes.",
                    'metrics': {
                        'loc': stats['loc'],
                        'functions': stats['num_functions'],
                        'classes': stats['num_classes'],
                        'threshold': int(god_threshold),
                    },
                    'why_problem': "Large files are harder to understand, test, and maintain. "
                                 "They often violate Single Responsibility Principle.",
                })
    
    def _detect_long_functions(self):
        """Detect functions exceeding length threshold."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return
        
        # Threshold: 50 lines
        long_function_threshold = 50
        
        for file_path, stats in file_stats.items():
            avg_func_length = stats['average_function_length']
            
            if avg_func_length > long_function_threshold:
                self.detected_smells.append({
                    'type': 'Long Functions',
                    'file': file_path,
                    'severity': 'medium' if avg_func_length < 100 else 'high',
                    'description': f"Functions are too long (average: {int(avg_func_length)} lines). "
                                 f"Contains {stats['num_functions']} functions.",
                    'metrics': {
                        'average_function_length': avg_func_length,
                        'num_functions': stats['num_functions'],
                        'threshold': long_function_threshold,
                    },
                    'why_problem': "Long functions are difficult to understand, test, and reuse. "
                                 "They often do multiple things and have hidden bugs.",
                })
    
    def _detect_high_complexity(self):
        """Detect functions with high cyclomatic complexity."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return
        
        # Threshold: CC > 10 is complex, > 15 is very complex
        complexity_high = 10
        complexity_critical = 15
        
        for file_path, stats in file_stats.items():
            cc = stats['cyclomatic_complexity']
            
            if cc > complexity_high:
                severity = 'critical' if cc > complexity_critical else 'high'
                self.detected_smells.append({
                    'type': 'High Cyclomatic Complexity',
                    'file': file_path,
                    'severity': severity,
                    'description': f"High cyclomatic complexity: {int(cc)}. "
                                 f"This file has {cc - 1} decision points (if/for/while/except etc.).",
                    'metrics': {
                        'cyclomatic_complexity': cc,
                        'high_threshold': complexity_high,
                        'critical_threshold': complexity_critical,
                    },
                    'why_problem': "High complexity increases bug risk, testing effort, and cognitive load. "
                                 "Each decision point adds exponential test combinations.",
                })
    
    def _detect_tight_coupling(self):
        """Detect tight coupling (high fan-out)."""
        file_stats = self.stats.get('file_stats', {})
        repo_stats = self.stats.get('repo_stats', {})
        
        if not file_stats:
            return
        
        avg_fan_out = sum(stats['fan_out'] for stats in file_stats.values()) / len(file_stats)
        high_fan_out_threshold = avg_fan_out * 2
        
        for file_path, stats in file_stats.items():
            if stats['fan_out'] > high_fan_out_threshold:
                self.detected_smells.append({
                    'type': 'Tight Coupling',
                    'file': file_path,
                    'severity': 'medium',
                    'description': f"File depends on too many other modules ({stats['fan_out']} dependencies). "
                                 f"Average is {int(avg_fan_out)} dependencies.",
                    'metrics': {
                        'fan_out': stats['fan_out'],
                        'average_fan_out': avg_fan_out,
                        'threshold': int(high_fan_out_threshold),
                    },
                    'why_problem': "Too many dependencies make code fragile and difficult to test. "
                                 "Changes in dependencies have cascading effects.",
                })
    
    def _detect_unused_code(self):
        """Detect potentially unused code (not called in call graph)."""
        symbol_table = self.symbol_table
        call_graph = self.call_graph
        
        if not call_graph or not symbol_table:
            return
        
        # Symbols in symbol table but not in call graph might be unused
        unused = []
        
        for symbol_name in symbol_table:
            if symbol_name not in call_graph and not symbol_name.startswith('_'):
                unused.append(symbol_name)
        
        if unused and len(unused) > 0:
            self.detected_smells.append({
                'type': 'Dead/Unused Code',
                'file': 'Multiple files',
                'severity': 'low',
                'description': f"Found {len(unused)} potentially unused symbols not referenced in call graph. "
                             f"Examples: {', '.join(unused[:5])}{'...' if len(unused) > 5 else ''}",
                'metrics': {
                    'unused_count': len(unused),
                    'examples': unused[:10],
                },
                'why_problem': "Dead code creates confusion, increases maintenance burden, "
                             "and makes it harder to understand what is actually used.",
            })
    
    def _detect_orphaned_files(self):
        """Detect orphaned files (no imports, not imported by others)."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return
        
        for file_path, stats in file_stats.items():
            fan_in = stats['fan_in']
            fan_out = stats['fan_out']
            
            # Orphaned = not imported by anyone, doesn't import from anywhere
            if fan_in == 0 and fan_out == 0 and not file_path.startswith('__'):
                self.detected_smells.append({
                    'type': 'Orphaned File',
                    'file': file_path,
                    'severity': 'medium',
                    'description': f"File is isolated with no imports and not imported by any other file. "
                                 f"May be dead code or incorrectly placed.",
                    'metrics': {
                        'fan_in': 0,
                        'fan_out': 0,
                        'loc': stats['loc'],
                    },
                    'why_problem': "Orphaned files indicate potential dead code or organizational issues. "
                                 "They may indicate incomplete refactoring or misplaced functionality.",
                })
    
    def _detect_hotspots(self):
        """Detect hotspots: frequently changed, highly coupled, complex files."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return
        
        # Calculate hotspot score for each file
        hotspots = []
        
        for file_path, stats in file_stats.items():
            # Hotspot = combination of complexity, size, and fan-out
            complexity_score = min(stats['cyclomatic_complexity'] / 10, 1.0)
            size_score = min(stats['loc'] / 500, 1.0)
            coupling_score = min(stats['fan_out'] / 20, 1.0)
            
            hotspot_score = (complexity_score * 0.4 + size_score * 0.3 + coupling_score * 0.3)
            
            if hotspot_score > 0.5:
                hotspots.append({
                    'file': file_path,
                    'score': hotspot_score,
                    'stats': stats,
                })
        
        # Report top hotspots
        for hotspot in sorted(hotspots, key=lambda x: x['score'], reverse=True)[:5]:
            self.detected_smells.append({
                'type': 'Change Hotspot',
                'file': hotspot['file'],
                'severity': 'medium' if hotspot['score'] < 0.7 else 'high',
                'description': f"File is a change hotspot: complex ({int(hotspot['stats']['cyclomatic_complexity'])} CC), "
                             f"large ({hotspot['stats']['loc']} LOC), "
                             f"and tightly coupled ({hotspot['stats']['fan_out']} dependencies).",
                'metrics': {
                    'hotspot_score': hotspot['score'],
                    'complexity': hotspot['stats']['cyclomatic_complexity'],
                    'loc': hotspot['stats']['loc'],
                    'fan_out': hotspot['stats']['fan_out'],
                },
                'why_problem': "Hotspot files are high-risk: changes are frequent and error-prone. "
                             "They accumulate complexity and create maintenance burden.",
            })
