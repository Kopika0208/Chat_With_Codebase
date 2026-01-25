"""
Standalone utility to generate Code Health analysis reports.
Can be run independently of the Streamlit app.
"""

import sys
import os
import json
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from code_health.stats import CodeStatistics
from code_health.health_score import HealthScoreCalculator
from code_health.smells import CodeSmellDetector
from code_health.refactoring import RefactoringAdvisor
from code_health.exporter import AnalysisExporter


def analyze_repository(repo_path: str, call_graph_path: Optional[str] = None, 
                      symbol_table_path: Optional[str] = None, 
                      output_dir: str = "code_health") -> None:
    """
    Analyze a repository and generate code health reports.
    
    Args:
        repo_path: Path to repository source files
        call_graph_path: Path to call_graph.json (optional)
        symbol_table_path: Path to symbol_table.json (optional)
        output_dir: Directory to save output files
    """
    print(f"🔍 Analyzing repository: {repo_path}")
    
    # Load call graph and symbol table if available
    call_graph = {}
    symbol_table = {}
    
    if call_graph_path and os.path.exists(call_graph_path):
        try:
            with open(call_graph_path) as f:
                call_graph = json.load(f)
            print(f"✓ Loaded call graph from {call_graph_path}")
        except Exception as e:
            print(f"⚠️ Could not load call graph: {e}")
    
    if symbol_table_path and os.path.exists(symbol_table_path):
        try:
            with open(symbol_table_path) as f:
                symbol_table = json.load(f)
            print(f"✓ Loaded symbol table from {symbol_table_path}")
        except Exception as e:
            print(f"⚠️ Could not load symbol table: {e}")
    
    # Compute statistics
    print("\n📊 Computing code statistics...")
    stats_computer = CodeStatistics(repo_path, call_graph, symbol_table)
    stats = stats_computer.compute_all_statistics()
    print(f"✓ Analyzed {stats.get('repo_stats', {}).get('num_files', 0)} files")
    
    # Calculate health score
    print("\n📈 Calculating code health score...")
    health_calculator = HealthScoreCalculator(stats, call_graph, symbol_table)
    health_result = health_calculator.calculate_overall_health()
    file_scores = health_calculator.calculate_file_scores()
    
    overall_score = health_result['overall_score']
    grade = health_result['interpretation']['grade']
    print(f"✓ Overall Health Score: {overall_score:.1f}/100 (Grade: {grade})")
    
    # Detect code smells
    print("\n🐛 Detecting code smells...")
    smell_detector = CodeSmellDetector(stats, call_graph, symbol_table, repo_path)
    smells = smell_detector.detect_all_smells()
    print(f"✓ Detected {len(smells)} code smell(s)")
    
    # Generate refactoring suggestions
    print("\n🔨 Generating refactoring suggestions...")
    advisor = RefactoringAdvisor(smells, stats)
    suggestions = advisor.generate_suggestions()
    print(f"✓ Generated {len(suggestions)} suggestion(s)")
    
    # Export results
    print(f"\n💾 Exporting results to {output_dir}/...")
    exporter = AnalysisExporter(output_dir)
    
    stats_file = exporter.export_statistics(stats)
    print(f"✓ Saved statistics: {stats_file}")
    
    health_file = exporter.export_health_score(health_result)
    print(f"✓ Saved health score: {health_file}")
    
    smells_file = exporter.export_smells(smells)
    print(f"✓ Saved code smells: {smells_file}")
    
    suggestions_file = exporter.export_refactoring_suggestions(suggestions)
    print(f"✓ Saved refactoring suggestions: {suggestions_file}")
    
    report_file = exporter.export_full_report(health_result, stats, smells, suggestions)
    print(f"✓ Saved comprehensive report: {report_file}")
    
    # Print summary
    print("\n" + "="*60)
    print("📊 ANALYSIS SUMMARY")
    print("="*60)
    print(f"Overall Health Score: {overall_score:.1f}/100 ({grade})")
    print(f"Files Analyzed: {stats.get('repo_stats', {}).get('num_files', 0)}")
    print(f"Total LOC: {stats.get('repo_stats', {}).get('total_loc', 0)}")
    print(f"Code Smells: {len(smells)}")
    print(f"Refactoring Suggestions: {len(suggestions)}")
    print("\nDimension Scores:")
    for dim, score in health_result['dimension_scores'].items():
        dim_name = dim.replace('_', ' ').title()
        print(f"  - {dim_name}: {score:.1f}/100")
    print("="*60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate Code Health & Quality analysis reports"
    )
    parser.add_argument(
        "repo_path",
        help="Path to repository source files"
    )
    parser.add_argument(
        "--call-graph",
        help="Path to call_graph.json",
        default=None
    )
    parser.add_argument(
        "--symbol-table",
        help="Path to symbol_table.json",
        default=None
    )
    parser.add_argument(
        "--output",
        help="Output directory for reports",
        default="code_health"
    )
    
    args = parser.parse_args()
    
    # Validate repo path
    if not os.path.isdir(args.repo_path):
        print(f"❌ Error: Repository path does not exist: {args.repo_path}")
        sys.exit(1)
    
    try:
        analyze_repository(
            args.repo_path,
            args.call_graph,
            args.symbol_table,
            args.output
        )
        print("\n✅ Analysis complete!")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
