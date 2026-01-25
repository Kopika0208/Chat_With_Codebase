"""
Output generation for Code Health analysis.
Saves analysis results to JSON and Markdown files.
"""

import json
import os
from typing import Dict, List
from datetime import datetime


class AnalysisExporter:
    """Exports code health analysis to JSON and Markdown files."""
    
    def __init__(self, output_dir: str = "code_health"):
        """
        Initialize exporter.
        
        Args:
            output_dir: Directory to save output files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def export_statistics(self, stats: Dict) -> str:
        """
        Export code statistics to JSON.
        
        Args:
            stats: Statistics dictionary
        
        Returns:
            Path to generated file
        """
        file_path = os.path.join(self.output_dir, "stats.json")
        
        with open(file_path, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        
        return file_path
    
    def export_health_score(self, health_result: Dict) -> str:
        """
        Export health score to JSON.
        
        Args:
            health_result: Health score calculation result
        
        Returns:
            Path to generated file
        """
        file_path = os.path.join(self.output_dir, "health_score.json")
        
        with open(file_path, 'w') as f:
            json.dump(health_result, f, indent=2, default=str)
        
        return file_path
    
    def export_smells(self, smells: List[Dict]) -> str:
        """
        Export detected code smells to JSON.
        
        Args:
            smells: List of detected smells
        
        Returns:
            Path to generated file
        """
        file_path = os.path.join(self.output_dir, "smells.json")
        
        with open(file_path, 'w') as f:
            json.dump(smells, f, indent=2, default=str)
        
        return file_path
    
    def export_refactoring_suggestions(self, suggestions: List[Dict]) -> str:
        """
        Export refactoring suggestions to Markdown.
        
        Args:
            suggestions: List of refactoring suggestions
        
        Returns:
            Path to generated file
        """
        file_path = os.path.join(self.output_dir, "refactor_suggestions.md")
        
        with open(file_path, 'w') as f:
            f.write("# Refactoring Suggestions\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            if not suggestions:
                f.write("No refactoring suggestions at this time.\n")
                return file_path
            
            f.write(f"## Summary\n\n")
            f.write(f"Total suggestions: {len(suggestions)}\n\n")
            
            # Count by priority
            by_priority = {'high': 0, 'medium': 0, 'low': 0}
            for sugg in suggestions:
                priority = sugg.get('priority', 'medium').lower()
                by_priority[priority] += 1
            
            f.write(f"- High Priority: {by_priority['high']}\n")
            f.write(f"- Medium Priority: {by_priority['medium']}\n")
            f.write(f"- Low Priority: {by_priority['low']}\n\n")
            
            f.write("---\n\n")
            
            # Detailed suggestions
            for i, suggestion in enumerate(suggestions, 1):
                f.write(f"## #{i} {suggestion['smell_type']}\n\n")
                f.write(f"**File:** `{suggestion['file']}`\n\n")
                
                priority = suggestion['priority'].upper()
                effort = suggestion['effort'].upper()
                f.write(f"**Priority:** {priority} | **Effort:** {effort}\n\n")
                
                if suggestion.get('description'):
                    f.write(f"### Problem\n\n{suggestion['description']}\n\n")
                
                if suggestion.get('rationale'):
                    f.write(f"### Rationale\n\n{suggestion['rationale']}\n\n")
                
                # Strategies
                strategies = suggestion.get('strategies', [])
                if strategies:
                    f.write(f"### Suggested Strategies\n\n")
                    
                    for j, strategy in enumerate(strategies, 1):
                        f.write(f"#### {j}. {strategy['name']}\n\n")
                        f.write(f"{strategy['description']}\n\n")
                        
                        f.write("**Steps:**\n\n")
                        for step in strategy.get('steps', []):
                            f.write(f"- {step}\n")
                        f.write("\n")
                        
                        if strategy.get('benefit'):
                            f.write(f"**Benefit:** {strategy['benefit']}\n\n")
                
                # Affected files
                affected = suggestion.get('affected_files', [])
                if affected:
                    f.write(f"### Affected Files\n\n")
                    for file in affected:
                        f.write(f"- `{file}`\n")
                    f.write("\n")
                
                f.write("---\n\n")
        
        return file_path
    
    def export_full_report(self, health_result: Dict, stats: Dict, smells: List[Dict], 
                          suggestions: List[Dict]) -> str:
        """
        Export comprehensive report as Markdown.
        
        Args:
            health_result: Health score result
            stats: Statistics dictionary
            smells: List of code smells
            suggestions: List of refactoring suggestions
        
        Returns:
            Path to generated file
        """
        file_path = os.path.join(self.output_dir, "CODE_HEALTH_REPORT.md")
        
        repo_stats = stats.get('repo_stats', {})
        
        with open(file_path, 'w') as f:
            # Header
            f.write("# Code Health & Quality Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Overall Score
            overall_score = health_result['overall_score']
            grade = health_result['interpretation']['grade']
            level = health_result['interpretation']['level']
            
            f.write(f"## Overall Health Score: {overall_score:.1f}/100 (Grade: {grade} - {level})\n\n")
            f.write(f"{health_result['interpretation']['description']}\n\n")
            
            f.write("---\n\n")
            
            # Dimension Scores
            f.write("## Health Dimensions\n\n")
            for dim, score in health_result['dimension_scores'].items():
                dim_name = dim.replace('_', ' ').title()
                f.write(f"- **{dim_name}:** {score:.1f}/100\n")
            f.write("\n")
            
            # Statistics
            f.write("## Code Statistics\n\n")
            f.write("### Repository Summary\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Total Files | {repo_stats.get('num_files', 0)} |\n")
            f.write(f"| Total LOC | {repo_stats.get('total_loc', 0)} |\n")
            f.write(f"| Code LOC | {repo_stats.get('total_loc_code', 0)} |\n")
            f.write(f"| Comment LOC | {repo_stats.get('total_loc_comment', 0)} |\n")
            f.write(f"| Blank Lines | {repo_stats.get('loc_blank', 0)} |\n")
            f.write(f"| Functions | {repo_stats.get('num_functions', 0)} |\n")
            f.write(f"| Classes | {repo_stats.get('num_classes', 0)} |\n")
            f.write(f"| Modules | {repo_stats.get('num_modules', 0)} |\n")
            f.write(f"| Avg Function Length | {repo_stats.get('avg_function_length', 0):.1f} |\n")
            f.write(f"| Avg Cyclomatic Complexity | {repo_stats.get('avg_cyclomatic_complexity', 0):.2f} |\n")
            f.write(f"| Comment-to-Code Ratio | {repo_stats.get('comment_to_code_ratio', 0):.2f} |\n\n")
            
            # Code Smells
            f.write("## Code Smells\n\n")
            if smells:
                f.write(f"Total smells detected: {len(smells)}\n\n")
                
                smells_by_type = {}
                for smell in smells:
                    smell_type = smell['type']
                    if smell_type not in smells_by_type:
                        smells_by_type[smell_type] = []
                    smells_by_type[smell_type].append(smell)
                
                for smell_type in sorted(smells_by_type.keys()):
                    type_smells = smells_by_type[smell_type]
                    f.write(f"### {smell_type} ({len(type_smells)})\n\n")
                    
                    for smell in type_smells:
                        f.write(f"- **File:** `{smell.get('file', 'Unknown')}`\n")
                        f.write(f"  - **Severity:** {smell.get('severity', 'medium').upper()}\n")
                        f.write(f"  - **Description:** {smell.get('description', 'N/A')}\n")
                        f.write(f"  - **Why it's a problem:** {smell.get('why_problem', 'N/A')}\n\n")
            else:
                f.write("No code smells detected. Excellent!\n\n")
            
            f.write("---\n\n")
            
            # Refactoring Suggestions
            f.write("## Refactoring Suggestions\n\n")
            if suggestions:
                f.write(f"Total suggestions: {len(suggestions)}\n\n")
                
                for i, suggestion in enumerate(suggestions, 1):
                    f.write(f"### {i}. {suggestion['smell_type']} - `{suggestion['file']}`\n\n")
                    f.write(f"**Priority:** {suggestion['priority'].upper()} | "
                           f"**Effort:** {suggestion['effort'].upper()}\n\n")
                    
                    if suggestion.get('description'):
                        f.write(f"**Problem:** {suggestion['description']}\n\n")
                    
                    if suggestion.get('rationale'):
                        f.write(f"**Rationale:** {suggestion['rationale']}\n\n")
                    
                    strategies = suggestion.get('strategies', [])
                    if strategies:
                        f.write("**Strategies:**\n\n")
                        for strategy in strategies:
                            f.write(f"- **{strategy['name']}:** {strategy['description']}\n")
                    
                    f.write("\n---\n\n")
            else:
                f.write("No refactoring suggestions needed.\n\n")
        
        return file_path
