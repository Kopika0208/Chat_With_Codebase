"""Shared code health computation helpers."""

from typing import Dict


def normalize_symbol_table(symbol_table: dict) -> dict:
    """Flatten symbol table for smell/pattern detection."""
    if not symbol_table or not isinstance(symbol_table, dict):
        return {}
    if "global_index" not in symbol_table and "file_symbols" not in symbol_table:
        return symbol_table

    flattened = {}
    global_index = symbol_table.get("global_index", {})
    if isinstance(global_index, dict):
        for name, occurrences in global_index.get("global_symbols", {}).items():
            if isinstance(occurrences, list) and occurrences:
                first = occurrences[0]
                if isinstance(first, dict):
                    flattened[name] = {
                        "name": name,
                        "type": "function" if first.get("kind") == "function" else "class",
                    }
    return flattened


def compute_health_payload(repo_path: str, call_graph: Dict, symbol_table: Dict) -> Dict:
    """Run the full code-health pipeline and return the API payload."""
    from code_health.stats import CodeStatistics
    from code_health.health_score import HealthScoreCalculator
    from code_health.smells import CodeSmellDetector
    from code_health.refactoring import RefactoringAdvisor

    normalized_st = normalize_symbol_table(symbol_table)

    stats_computer = CodeStatistics(repo_path, call_graph, symbol_table)
    stats = stats_computer.compute_all_statistics()

    repo_stats = stats.get("repo_stats", {})
    if not repo_stats:
        return {
            "overall_score": 0,
            "grade": "N/A",
            "level": "Unknown",
            "description": "",
            "dimension_scores": {},
            "repo_stats": {},
            "smells": [],
            "suggestions": [],
            "file_scores": {},
        }

    health_calc = HealthScoreCalculator(stats, call_graph, normalized_st)
    health_result = health_calc.calculate_overall_health()
    file_scores = health_calc.calculate_file_scores()

    smell_detector = CodeSmellDetector(stats, call_graph, normalized_st, repo_path)
    smells = smell_detector.detect_all_smells()

    advisor = RefactoringAdvisor(smells, stats)
    suggestions = advisor.generate_suggestions()

    return {
        "overall_score": health_result.get("overall_score", 0),
        "grade": health_result.get("interpretation", {}).get("grade", "N/A"),
        "level": health_result.get("interpretation", {}).get("level", "Unknown"),
        "description": health_result.get("interpretation", {}).get("description", ""),
        "dimension_scores": health_result.get("dimension_scores", {}),
        "repo_stats": repo_stats,
        "smells": smells,
        "suggestions": suggestions[:20],
        "file_scores": {
            k: v for k, v in sorted(
                file_scores.items(), key=lambda x: x[1].get("score", 0)
            )[:20]
        },
    }
