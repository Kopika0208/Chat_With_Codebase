"""
Code Health Score calculation.
Computes weighted composite score (0-100) across multiple dimensions.
"""

from typing import Dict, Tuple
import json


class HealthScoreCalculator:
    """Calculates overall code health score."""
    
    # Normalization thresholds and weights
    THRESHOLDS = {
        'complexity_max': 15,
        'function_length_max': 50,
        'churn_max': 100,
        'fan_out_max': 20,
        'comment_ratio_min': 0.1,
    }
    
    WEIGHTS = {
        'maintainability': 0.25,
        'modularity': 0.25,
        'readability': 0.25,
        'change_risk': 0.15,
        'dependency_hygiene': 0.10,
    }
    
    def __init__(self, stats: Dict, call_graph: Dict, symbol_table: Dict):
        """
        Initialize health score calculator.
        
        Args:
            stats: Code statistics (from CodeStatistics.compute_all_statistics())
            call_graph: Call graph data
            symbol_table: Symbol table data
        """
        self.stats = stats if isinstance(stats, dict) else {}
        self.call_graph = call_graph if isinstance(call_graph, dict) else {}
        self.symbol_table = symbol_table if isinstance(symbol_table, dict) else {}
        self.dimension_scores = {}
        self.file_scores = {}
    
    def calculate_overall_health(self) -> Dict:
        """Calculate overall code health score."""
        self.dimension_scores = {
            'maintainability': self._score_maintainability(),
            'modularity': self._score_modularity(),
            'readability': self._score_readability(),
            'change_risk': self._score_change_risk(),
            'dependency_hygiene': self._score_dependency_hygiene(),
        }
        
        # Calculate weighted overall score
        overall_score = sum(
            self.dimension_scores[dim] * self.WEIGHTS[dim]
            for dim in self.dimension_scores
        )
        
        # Clamp to 0-100
        overall_score = max(0, min(100, overall_score))
        
        return {
            'overall_score': overall_score,
            'dimension_scores': self.dimension_scores,
            'interpretation': self._interpret_score(overall_score),
        }
    
    def _score_maintainability(self) -> float:
        """
        Score based on complexity and function length.
        Higher complexity/longer functions = lower score.
        """
        repo_stats = self.stats.get('repo_stats', {})
        
        avg_complexity = repo_stats.get('avg_cyclomatic_complexity', 5)
        avg_function_length = repo_stats.get('avg_function_length', 20)
        
        # Normalize complexity (1-5 is good, 10+ is bad)
        complexity_norm = max(0, (self.THRESHOLDS['complexity_max'] - avg_complexity) 
                              / self.THRESHOLDS['complexity_max'])
        
        # Normalize function length (20-50 lines is good)
        function_length_norm = max(0, 
            (self.THRESHOLDS['function_length_max'] - avg_function_length) 
            / self.THRESHOLDS['function_length_max']
        )
        
        # Weighted average
        score = (complexity_norm * 0.6 + function_length_norm * 0.4) * 100
        return max(0, min(100, score))
    
    def _score_modularity(self) -> float:
        """
        Score based on fan-in/fan-out balance and god file detection.
        Good modularity = balanced dependencies, no god files.
        """
        repo_stats = self.stats.get('repo_stats', {})
        file_stats = self.stats.get('file_stats', {})
        
        num_files = repo_stats.get('num_files', 1)
        
        if not file_stats or num_files == 0:
            return 50
        
        # Detect god files (files with disproportionate LOC)
        avg_file_loc = repo_stats.get('total_loc', 0) / max(num_files, 1)
        god_file_threshold = avg_file_loc * 3  # 3x average
        
        god_files = sum(1 for stats in file_stats.values() 
                       if stats['loc'] > god_file_threshold)
        
        # Compute average fan-out
        avg_fan_out = sum(stats['fan_out'] for stats in file_stats.values()) / max(len(file_stats), 1)
        
        # God files reduce score significantly
        god_file_penalty = (god_files / max(num_files, 1)) * 30
        
        # Fan-out penalty (too many dependencies)
        fan_out_norm = max(0, (self.THRESHOLDS['fan_out_max'] - avg_fan_out) 
                          / self.THRESHOLDS['fan_out_max'])
        
        score = (fan_out_norm * 100) - god_file_penalty
        return max(0, min(100, score))
    
    def _score_readability(self) -> float:
        """
        Score based on documentation coverage and comments.
        Higher docstring coverage and comments = higher score.
        """
        repo_stats = self.stats.get('repo_stats', {})
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return 50
        
        # Average docstring coverage
        avg_docstring_coverage = sum(stats['docstring_coverage'] for stats in file_stats.values()) / len(file_stats)
        
        # Average comment-to-code ratio
        avg_comment_ratio = repo_stats.get('comment_to_code_ratio', 0)
        
        # Documentation score (0-100 based on coverage)
        doc_score = avg_docstring_coverage
        
        # Comment score (0-100 based on ratio)
        comment_score = min(100, (avg_comment_ratio / 0.3) * 100)  # 30% ratio is ideal
        
        # Weighted average
        score = (doc_score * 0.6 + comment_score * 0.4)
        return max(0, min(100, score))
    
    def _score_change_risk(self) -> float:
        """
        Score based on churn and ownership concentration.
        High churn + concentrated ownership = higher risk = lower score.
        
        For now, use heuristics since git churn requires local git access.
        """
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return 50
        
        # Use file complexity as proxy for change risk
        # Complex files are harder to change safely
        avg_complexity = sum(stats['cyclomatic_complexity'] for stats in file_stats.values()) / len(file_stats)
        
        # Normalize: 1-5 is low risk, 10+ is high risk
        risk_norm = max(0, (self.THRESHOLDS['complexity_max'] - avg_complexity) 
                        / self.THRESHOLDS['complexity_max'])
        
        score = risk_norm * 100
        return max(0, min(100, score))
    
    def _score_dependency_hygiene(self) -> float:
        """
        Score based on dependency counts and unused imports.
        Lower dependency count + no unused imports = higher score.
        """
        repo_stats = self.stats.get('repo_stats', {})
        file_stats = self.stats.get('file_stats', {})
        
        if not file_stats:
            return 50
        
        # Average dependencies per file
        avg_dependencies = repo_stats.get('total_loc', 0) / max(len(file_stats), 1)
        
        # Too many dependencies = harder to test and understand
        # Threshold: 10 dependencies is reasonable
        dep_norm = max(0, (15 - avg_dependencies) / 15)
        
        # Check for circular dependencies (simplified)
        circular_penalty = self._detect_circular_dependencies() * 20
        
        score = (dep_norm * 100) - circular_penalty
        return max(0, min(100, score))
    
    def _detect_circular_dependencies(self) -> float:
        """
        Detect circular dependencies in call graph.
        Returns penalty factor (0-1).
        """
        if not self.call_graph:
            return 0
        
        visited = set()
        rec_stack = set()
        circular_count = 0
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            neighbors = self.call_graph.get(node, [])
            if isinstance(neighbors, dict):
                neighbors = list(neighbors.keys())
            elif not isinstance(neighbors, list):
                neighbors = [neighbors]
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        # Detect cycles
        for node in self.call_graph:
            if node not in visited:
                if has_cycle(node):
                    circular_count += 1
        
        # Return penalty as fraction of total nodes
        total_nodes = len(self.call_graph)
        return (circular_count / max(total_nodes, 1)) if total_nodes > 0 else 0
    
    def _interpret_score(self, score: float) -> Dict:
        """Provide interpretation of the score."""
        if score >= 80:
            return {
                'grade': 'A',
                'level': 'Excellent',
                'description': 'Code health is excellent. Maintain current practices.',
            }
        elif score >= 60:
            return {
                'grade': 'B',
                'level': 'Good',
                'description': 'Code health is good. Consider addressing detected smells.',
            }
        elif score >= 40:
            return {
                'grade': 'C',
                'level': 'Fair',
                'description': 'Code health needs improvement. Prioritize refactoring.',
            }
        else:
            return {
                'grade': 'D',
                'level': 'Poor',
                'description': 'Code health is poor. Major refactoring recommended.',
            }
    
    def calculate_file_scores(self) -> Dict:
        """Calculate health scores for individual files."""
        file_scores = {}
        file_stats = self.stats.get('file_stats', {})
        
        for file_path, stats in file_stats.items():
            # Combine multiple metrics into file-level score
            complexity_norm = max(0, (self.THRESHOLDS['complexity_max'] - stats['cyclomatic_complexity']) 
                                 / self.THRESHOLDS['complexity_max'])
            
            size_norm = max(0, (self.THRESHOLDS['function_length_max'] - stats['average_function_length']) 
                           / self.THRESHOLDS['function_length_max'])
            
            doc_norm = stats['docstring_coverage'] / 100.0
            
            # Weighted score
            file_score = (
                complexity_norm * 0.4 +
                size_norm * 0.3 +
                doc_norm * 0.3
            ) * 100
            
            file_scores[file_path] = {
                'score': max(0, min(100, file_score)),
                'complexity': stats['cyclomatic_complexity'],
                'loc': stats['loc'],
                'docstring_coverage': stats['docstring_coverage'],
            }
        
        return file_scores
