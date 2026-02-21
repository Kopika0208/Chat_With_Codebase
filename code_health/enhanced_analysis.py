"""
Enhanced Code Health Analysis Module.
Provides deeper insights into code quality with detailed metrics and actionable recommendations.
"""

from typing import Dict, List, Tuple
from collections import defaultdict
import statistics


class EnhancedHealthAnalyzer:
    """Advanced health analysis with detailed metrics."""
    
    HEALTH_THRESHOLDS = {
        'cyclomatic_complexity': {'ideal': 3, 'warning': 7, 'critical': 15},
        'lines_per_function': {'ideal': 15, 'warning': 50, 'critical': 100},
        'lines_per_class': {'ideal': 100, 'warning': 300, 'critical': 500},
        'function_parameters': {'ideal': 3, 'warning': 5, 'critical': 7},
        'docstring_coverage': {'ideal': 0.80, 'warning': 0.50, 'critical': 0.20},
        'comment_ratio': {'ideal': 0.15, 'warning': 0.05, 'critical': 0.01},
        'nesting_depth': {'ideal': 2, 'warning': 4, 'critical': 7},
    }
    
    def __init__(self, stats: Dict, call_graph: Dict, symbol_table: Dict):
        """Initialize enhanced analyzer."""
        self.stats = stats if isinstance(stats, dict) else {}
        self.call_graph = call_graph if isinstance(call_graph, dict) else {}
        self.symbol_table = symbol_table if isinstance(symbol_table, dict) else {}
    
    def get_detailed_health_report(self) -> Dict:
        """Generate comprehensive health report with all metrics."""
        return {
            'summary': self._generate_summary(),
            'dimension_analysis': self._analyze_all_dimensions(),
            'file_breakdown': self._analyze_file_distribution(),
            'trends': self._analyze_trends(),
            'risk_areas': self._identify_risk_areas(),
            'quality_indicators': self._calculate_quality_indicators(),
        }
    
    def _generate_summary(self) -> Dict:
        """Generate overall summary."""
        file_stats = self.stats.get('file_stats', {})
        repo_stats = self.stats.get('repo_stats', {})
        
        if not file_stats:
            return {}
        
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        functions = [f['num_functions'] for f in file_stats.values()]
        locs = [f['loc'] for f in file_stats.values()]
        
        return {
            'health_score': self._calculate_enhanced_score(),
            'status': self._get_status(),
            'total_files': repo_stats.get('num_files', 0),
            'total_functions': sum(functions),
            'total_classes': repo_stats.get('num_classes', 0),
            'total_loc': sum(locs),
            'avg_complexity': statistics.mean(complexities) if complexities else 0,
            'avg_function_length': statistics.mean([f['average_function_length'] for f in file_stats.values()]) if file_stats else 0,
            'complexity_std_dev': statistics.stdev(complexities) if len(complexities) > 1 else 0,
        }
    
    def _calculate_enhanced_score(self) -> float:
        """Calculate health score using enhanced algorithm."""
        file_stats = self.stats.get('file_stats', {})
        repo_stats = self.stats.get('repo_stats', {})
        
        if not file_stats:
            return 0
        
        scores = []
        
        # 1. Complexity Score (30% weight)
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        avg_cc = statistics.mean(complexities) if complexities else 5
        cc_score = self._calculate_metric_score(
            avg_cc,
            self.HEALTH_THRESHOLDS['cyclomatic_complexity']
        )
        scores.append(('Complexity', cc_score, 0.30))
        
        # 2. Function Length Score (20% weight)
        func_lengths = [f['average_function_length'] for f in file_stats.values()]
        avg_func_len = statistics.mean(func_lengths) if func_lengths else 30
        func_score = self._calculate_metric_score(
            avg_func_len,
            self.HEALTH_THRESHOLDS['lines_per_function'],
            inverse=True
        )
        scores.append(('Function Length', func_score, 0.20))
        
        # 3. Documentation Score (20% weight)
        docs = [f['docstring_coverage'] / 100.0 for f in file_stats.values()]
        avg_doc = statistics.mean(docs) if docs else 0.3
        doc_score = self._calculate_metric_score(
            avg_doc,
            {'ideal': 0.80, 'warning': 0.50, 'critical': 0.20},
            is_percentage=True
        )
        scores.append(('Documentation', doc_score, 0.20))
        
        # 4. Modularity Score (15% weight)
        modularity = self._calculate_modularity_score()
        scores.append(('Modularity', modularity, 0.15))
        
        # 5. Testing Score (15% weight)
        testing = self._calculate_testing_score()
        scores.append(('Testing', testing, 0.15))
        
        # Calculate weighted average
        total_score = sum(score * weight for _, score, weight in scores)
        return max(0, min(100, total_score))
    
    def _calculate_metric_score(self, value: float, thresholds: Dict, 
                               inverse: bool = False, is_percentage: bool = False) -> float:
        """Calculate score for a metric based on thresholds."""
        ideal = thresholds['ideal']
        warning = thresholds['warning']
        critical = thresholds['critical']
        
        if inverse:
            # For metrics where lower is better
            if value <= ideal:
                return 100
            elif value <= warning:
                return 75
            elif value <= critical:
                return 50
            else:
                return 25
        else:
            # For metrics where higher is better
            if value >= ideal:
                return 100
            elif value >= warning:
                return 75
            elif value >= critical:
                return 50
            else:
                return 25
    
    def _get_status(self) -> str:
        """Determine overall status."""
        score = self._calculate_enhanced_score()
        if score >= 80:
            return "EXCELLENT"
        elif score >= 60:
            return "GOOD"
        elif score >= 40:
            return "FAIR"
        else:
            return "POOR"
    
    def _analyze_all_dimensions(self) -> Dict:
        """Analyze all health dimensions."""
        return {
            'complexity': self._analyze_complexity(),
            'size': self._analyze_size(),
            'documentation': self._analyze_documentation(),
            'dependencies': self._analyze_dependencies(),
            'testing': self._analyze_testing_potential(),
            'duplication': self._analyze_duplication(),
        }
    
    def _analyze_complexity(self) -> Dict:
        """Analyze complexity metrics."""
        file_stats = self.stats.get('file_stats', {})
        repo_stats = self.stats.get('repo_stats', {})
        
        if not file_stats:
            return {}
        
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        
        return {
            'average': statistics.mean(complexities),
            'max': max(complexities),
            'min': min(complexities),
            'std_dev': statistics.stdev(complexities) if len(complexities) > 1 else 0,
            'high_complexity_files': sum(1 for c in complexities if c > 10),
            'score': self._calculate_metric_score(
                statistics.mean(complexities),
                self.HEALTH_THRESHOLDS['cyclomatic_complexity']
            ),
        }
    
    def _analyze_size(self) -> Dict:
        """Analyze code size metrics."""
        file_stats = self.stats.get('file_stats', {})
        repo_stats = self.stats.get('repo_stats', {})
        
        if not file_stats:
            return {}
        
        locs = [f['loc'] for f in file_stats.values()]
        func_lengths = [f['average_function_length'] for f in file_stats.values()]
        
        return {
            'total_loc': sum(locs),
            'avg_file_loc': statistics.mean(locs),
            'max_file_loc': max(locs),
            'avg_function_length': statistics.mean(func_lengths),
            'max_function_length': max(func_lengths),
            'large_files': sum(1 for loc in locs if loc > 500),
            'very_large_files': sum(1 for loc in locs if loc > 1000),
            'score': self._calculate_metric_score(
                statistics.mean(func_lengths),
                self.HEALTH_THRESHOLDS['lines_per_function'],
                inverse=True
            ),
        }
    
    def _analyze_documentation(self) -> Dict:
        """Analyze documentation metrics."""
        file_stats = self.stats.get('file_stats', {})
        repo_stats = self.stats.get('repo_stats', {})
        
        if not file_stats:
            return {}
        
        docs = [f['docstring_coverage'] / 100.0 for f in file_stats.values()]
        
        return {
            'avg_docstring_coverage': statistics.mean(docs) * 100,
            'files_with_poor_docs': sum(1 for d in docs if d < 0.3),
            'files_with_no_docs': sum(1 for d in docs if d == 0),
            'comment_ratio': repo_stats.get('comment_to_code_ratio', 0),
            'score': self._calculate_metric_score(
                statistics.mean(docs),
                {'ideal': 0.80, 'warning': 0.50, 'critical': 0.20},
                is_percentage=True
            ),
        }
    
    def _analyze_dependencies(self) -> Dict:
        """Analyze dependency metrics."""
        if not self.call_graph:
            return {}
        
        # Calculate fan-in and fan-out
        fan_in = defaultdict(int)
        fan_out = defaultdict(int)
        
        for caller, callees in self.call_graph.items():
            callees_list = list(callees) if isinstance(callees, (set, list)) else [callees]
            fan_out[caller] = len(callees_list)
            for callee in callees_list:
                fan_in[callee] += 1
        
        avg_fan_in = statistics.mean(list(fan_in.values())) if fan_in else 0
        avg_fan_out = statistics.mean(list(fan_out.values())) if fan_out else 0
        
        return {
            'avg_fan_in': avg_fan_in,
            'avg_fan_out': avg_fan_out,
            'max_fan_in': max(fan_in.values()) if fan_in else 0,
            'max_fan_out': max(fan_out.values()) if fan_out else 0,
            'high_coupling_items': sum(1 for f in fan_out.values() if f > 10),
            'score': max(0, 100 - (avg_fan_out * 5)),  # Penalty for high fan-out
        }
    
    def _analyze_testing_potential(self) -> Dict:
        """Estimate testing potential."""
        file_stats = self.stats.get('file_stats', {})
        repo_stats = self.stats.get('repo_stats', {})
        
        if not file_stats:
            return {}
        
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        
        # Test complexity: higher complexity requires more tests
        avg_complexity = statistics.mean(complexities) if complexities else 1
        required_test_cases = sum(complexities)  # Cyclomatic complexity indicates test paths
        
        return {
            'estimated_test_paths': required_test_cases,
            'avg_complexity': avg_complexity,
            'easily_testable_files': sum(1 for c in complexities if c <= 5),
            'hard_to_test_files': sum(1 for c in complexities if c > 10),
        }
    
    def _analyze_duplication(self) -> Dict:
        """Analyze code duplication potential."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return {}
        
        # Simple heuristic: similar function names in different files suggest duplication
        function_names = defaultdict(list)
        for file_path, stats in file_stats.items():
            if 'functions' in stats:
                for func_name in stats.get('functions', []):
                    function_names[func_name].append(file_path)
        
        duplicated_functions = sum(1 for funcs in function_names.values() if len(funcs) > 1)
        
        return {
            'potential_duplicate_functions': duplicated_functions,
            'duplication_risk': 'high' if duplicated_functions > 5 else ('medium' if duplicated_functions > 0 else 'low'),
        }
    
    def _analyze_file_distribution(self) -> Dict:
        """Analyze how code is distributed across files."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return {}
        
        locs = [f['loc'] for f in file_stats.values()]
        sorted_files = sorted(file_stats.items(), key=lambda x: x[1]['loc'], reverse=True)
        
        return {
            'total_files': len(file_stats),
            'top_5_largest': [
                {'file': f[0], 'loc': f[1]['loc'], 'functions': f[1].get('num_functions', 0)}
                for f in sorted_files[:5]
            ],
            'loc_distribution': {
                'tiny': sum(1 for loc in locs if loc < 50),
                'small': sum(1 for loc in locs if 50 <= loc < 150),
                'medium': sum(1 for loc in locs if 150 <= loc < 300),
                'large': sum(1 for loc in locs if 300 <= loc < 500),
                'very_large': sum(1 for loc in locs if loc >= 500),
            },
        }
    
    def _analyze_trends(self) -> Dict:
        """Analyze code quality trends."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return {}
        
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        
        return {
            'complexity_variance': statistics.stdev(complexities) if len(complexities) > 1 else 0,
            'consistency': 'high' if statistics.stdev(complexities) < 3 else ('medium' if statistics.stdev(complexities) < 7 else 'low'),
            'hotspots_detected': self._detect_hotspots(),
        }
    
    def _identify_risk_areas(self) -> List[Dict]:
        """Identify high-risk areas."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return []
        
        risk_areas = []
        
        for file_path, stats in file_stats.items():
            risk_score = 0
            reasons = []
            
            if stats['cyclomatic_complexity'] > 10:
                risk_score += 30
                reasons.append(f"High complexity ({stats['cyclomatic_complexity']})")
            
            if stats['loc'] > 500:
                risk_score += 25
                reasons.append(f"Large file ({stats['loc']} LOC)")
            
            if stats['docstring_coverage'] < 30:
                risk_score += 15
                reasons.append(f"Low documentation ({stats['docstring_coverage']}%)")
            
            if risk_score > 0:
                risk_areas.append({
                    'file': file_path,
                    'risk_score': min(100, risk_score),
                    'reasons': reasons,
                })
        
        return sorted(risk_areas, key=lambda x: x['risk_score'], reverse=True)
    
    def _calculate_quality_indicators(self) -> Dict:
        """Calculate overall quality indicators."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return {}
        
        return {
            'maintainability_index': self._calculate_maintainability_index(),
            'technical_debt_estimate': self._estimate_technical_debt(),
            'refactoring_priority': self._determine_refactoring_priority(),
        }
    
    def _calculate_maintainability_index(self) -> float:
        """Calculate Maintainability Index (0-100)."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return 50
        
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        lines = [f['loc'] for f in file_stats.values()]
        docs = [f['docstring_coverage'] / 100.0 for f in file_stats.values()]
        
        avg_cc = statistics.mean(complexities) if complexities else 1
        avg_lines = statistics.mean(lines) if lines else 100
        avg_doc = statistics.mean(docs) if docs else 0.3
        
        # Simplified formula
        mi = 171 - (5.2 * (avg_cc ** 1.5)) - (0.023 * avg_lines) + (50 * avg_doc)
        return max(0, min(100, mi))
    
    def _estimate_technical_debt(self) -> str:
        """Estimate technical debt."""
        score = self._calculate_enhanced_score()
        
        if score >= 80:
            return "Low - Code base is well-maintained"
        elif score >= 60:
            return "Moderate - Some refactoring recommended"
        elif score >= 40:
            return "High - Significant refactoring needed"
        else:
            return "Critical - Major refactoring required immediately"
    
    def _determine_refactoring_priority(self) -> List[str]:
        """Determine priority areas for refactoring."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return []
        
        priorities = []
        
        # Check complexity
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        if statistics.mean(complexities) > 8:
            priorities.append("Reduce cyclomatic complexity in high-complexity units")
        
        # Check size
        locs = [f['loc'] for f in file_stats.values()]
        if max(locs) > 500:
            priorities.append("Break down large files into smaller modules")
        
        # Check documentation
        docs = [f['docstring_coverage'] / 100.0 for f in file_stats.values()]
        if statistics.mean(docs) < 0.5:
            priorities.append("Improve documentation and comments")
        
        return priorities
    
    def _calculate_modularity_score(self) -> float:
        """Calculate modularity score."""
        if not self.call_graph:
            return 50
        
        fan_out = defaultdict(int)
        for caller, callees in self.call_graph.items():
            callees_list = list(callees) if isinstance(callees, (set, list)) else [callees]
            fan_out[caller] = len(callees_list)
        
        avg_fan_out = statistics.mean(list(fan_out.values())) if fan_out else 0
        return max(0, 100 - (avg_fan_out * 2))
    
    def _calculate_testing_score(self) -> float:
        """Calculate testing difficulty score."""
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return 50
        
        complexities = [f['cyclomatic_complexity'] for f in file_stats.values()]
        avg_cc = statistics.mean(complexities) if complexities else 1
        
        # Lower complexity = higher testability
        return max(0, 100 - (avg_cc * 3))
    
    def _detect_hotspots(self) -> List[str]:
        """Detect hotspots in the code."""
        if not self.call_graph:
            return []
        
        # Functions called frequently are hotspots
        call_counts = defaultdict(int)
        
        for caller, callees in self.call_graph.items():
            callees_list = list(callees) if isinstance(callees, (set, list)) else [callees]
            for callee in callees_list:
                call_counts[callee] += 1
        
        # Get top 5 most-called functions
        hotspots = sorted(call_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        return [item[0] for item in hotspots]
