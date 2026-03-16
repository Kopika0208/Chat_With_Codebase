"""
Code Smell Detection.
Identifies common code smells using heuristics and metrics.
Uses LLM (Groq) for context-aware pattern analysis with fallback to hardcoded detection.
"""

from typing import Dict, List, Optional
import re
import json
import os

# Try to import LLM from cache, fallback to None if unavailable
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from retrieval.cache import get_llm
    HAS_LLM = True
except Exception:
    get_llm = None
    HAS_LLM = False


class CodeSmellDetector:
    """Detects common code smells."""
    
    def __init__(self, stats: Dict, call_graph: Dict, symbol_table: Dict, repo_path: str, use_llm: bool = True):
        """
        Initialize smell detector.
        
        Args:
            stats: Code statistics
            call_graph: Call graph data
            symbol_table: Symbol table data
            repo_path: Path to repository
            use_llm: Whether to use LLM for enhanced analysis
        """
        self.stats = stats if isinstance(stats, dict) else {}
        self.call_graph = call_graph if isinstance(call_graph, dict) else {}
        self.symbol_table = symbol_table if isinstance(symbol_table, dict) else {}
        self.repo_path = repo_path
        self.detected_smells = []
        self.use_llm = use_llm and HAS_LLM
        self.llm = None
        
        if self.use_llm:
            try:
                self.llm = get_llm()
            except Exception:
                self.use_llm = False
                self.llm = None
    
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
        self._detect_design_patterns()
        
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
    
    def _detect_design_patterns(self):
        """Detect common design patterns with LLM enhancement."""
        patterns_detected = self._detect_raw_design_patterns()
        
        # Try LLM enhancement if available
        if self.use_llm and self.llm and patterns_detected:
            enhanced = self._enhance_patterns_with_llm(patterns_detected)
            if enhanced:
                self.detected_smells.append(enhanced)
                return
        
        # Fallback to basic pattern reporting
        if patterns_detected:
            self.detected_smells.append({
                'type': 'Design Patterns Detected',
                'file': 'Architecture',
                'severity': 'info',
                'description': f"Detected {len(patterns_detected)} design patterns in codebase.",
                'patterns': patterns_detected,
                'metrics': {
                    'total_patterns': len(patterns_detected),
                    'pattern_types': list(set(p['pattern'] for p in patterns_detected)),
                },
                'why_problem': "Design patterns indicate architectural structure. This is informational.",
            })
    
    def _detect_raw_design_patterns(self) -> List[Dict]:
        """Detect raw design patterns without LLM."""
        symbol_table = self.symbol_table
        patterns_detected = []
        
        if not symbol_table:
            return patterns_detected
        
        # Pattern 1: Singleton Detection
        for symbol_name, symbol_data in symbol_table.items():
            if isinstance(symbol_data, dict) and symbol_data.get('kind') == 'class':
                class_name = symbol_name.split('::')[-1] if '::' in symbol_name else symbol_name
                has_private_constructor = any(
                    '__init__' in s or 'private' in str(s)
                    for s in symbol_table.keys()
                    if class_name in str(s)
                )
                has_static_getter = any(
                    ('instance' in s.lower() or 'getinstance' in s.lower())
                    and ('static' in str(symbol_table.get(s, {})) or s.startswith('get_'))
                    for s in symbol_table.keys()
                    if class_name in str(s)
                )
                if has_private_constructor and has_static_getter:
                    patterns_detected.append({
                        'pattern': 'Singleton',
                        'location': symbol_name,
                        'confidence': 0.85,
                        'description': f"Class {class_name} shows Singleton pattern characteristics.",
                    })
        
        # Pattern 2: Factory Pattern Detection
        for symbol_name in symbol_table.keys():
            if isinstance(symbol_name, str):
                if any(pattern in symbol_name.lower() for pattern in ['create_', 'make_', 'factory']):
                    if 'static' in str(symbol_table.get(symbol_name, {})):
                        patterns_detected.append({
                            'pattern': 'Factory',
                            'location': symbol_name,
                            'confidence': 0.80,
                            'description': f"Method {symbol_name} matches Factory pattern.",
                        })
        
        # Pattern 3: Observer Pattern Detection
        has_subscribe = any(
            'subscribe' in s.lower() or 'add_listener' in s.lower() or 'attach' in s.lower()
            for s in symbol_table.keys()
        )
        has_notify = any(
            'notify' in s.lower() or 'fire' in s.lower() or 'emit' in s.lower()
            for s in symbol_table.keys()
        )
        if has_subscribe and has_notify:
            patterns_detected.append({
                'pattern': 'Observer',
                'location': 'Multiple classes',
                'confidence': 0.70,
                'description': "Codebase shows Observer pattern.",
            })
        
        # Pattern 4: Adapter/Wrapper Detection
        adapter_candidates = [
            s for s in symbol_table.keys()
            if isinstance(s, str) and ('adapter' in s.lower() or 'wrapper' in s.lower())
        ]
        if adapter_candidates:
            patterns_detected.append({
                'pattern': 'Adapter/Wrapper',
                'location': ', '.join(adapter_candidates[:3]),
                'confidence': 0.75,
                'examples': adapter_candidates[:5],
                'description': f"Found {len(adapter_candidates)} Adapter/Wrapper pattern candidates.",
            })
        
        # Pattern 5: Decorator Detection
        decorator_candidates = [
            s for s in symbol_table.keys()
            if isinstance(s, str) and ('decor' in s.lower() or 'wrap' in s.lower())
        ]
        if decorator_candidates:
            patterns_detected.append({
                'pattern': 'Decorator',
                'location': ', '.join(decorator_candidates[:3]),
                'confidence': 0.75,
                'examples': decorator_candidates[:5],
                'description': f"Found {len(decorator_candidates)} Decorator pattern candidates.",
            })
        
        return patterns_detected
    
    def _enhance_patterns_with_llm(self, patterns_detected: List[Dict]) -> Optional[Dict]:
        """Enhance pattern detection with LLM insights."""
        if not self.llm or not patterns_detected:
            return None
        
        try:
            prompt = f"""You are a software architect analyzing design patterns in a codebase.

DETECTED PATTERNS: {len(patterns_detected)}
PATTERN TYPES: {', '.join(set(p['pattern'] for p in patterns_detected))}

PATTERN DETAILS:
{json.dumps(patterns_detected[:5], indent=2)}

Provide JSON response with:
{{  
    "architecture_insights": "Analysis of architectural choices",
    "strengths": ["Strength 1"],
    "concerns": ["Concern 1"],
    "recommendations": ["Recommendation 1"],
    "maturity": "basic|intermediate|advanced"
}}"""
            
            response = self.llm.invoke(prompt)
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0]
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0]
            
            llm_insight = json.loads(json_str)
            
            return {
                'type': 'Design Patterns Detected',
                'file': 'Architecture',
                'severity': 'info',
                'description': llm_insight.get('architecture_insights', ''),
                'patterns': patterns_detected,
                'metrics': {
                    'total_patterns': len(patterns_detected),
                    'pattern_types': list(set(p['pattern'] for p in patterns_detected)),
                    'maturity': llm_insight.get('maturity', 'intermediate'),
                },
                'strengths': llm_insight.get('strengths', []),
                'concerns': llm_insight.get('concerns', []),
                'recommendations': llm_insight.get('recommendations', []),
                'why_problem': "Design patterns indicate architectural structure. This is informational.",
            }
        except Exception:
            return None