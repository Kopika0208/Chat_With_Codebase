# Code Health & Quality Analysis

Comprehensive static analysis suite for computing code health metrics, detecting code smells, and generating refactoring suggestions.

## Features

### 📊 Code Statistics
- **File-level metrics**: LOC, complexity, function/class counts, docstring coverage, fan-in/fan-out
- **Module-level aggregation**: Organized statistics by module
- **Repository-level summary**: Overall codebase health metrics

### 💪 Health Score Calculation
Weighted composite score (0-100) across five dimensions:
- **Maintainability** (25%): Function length, cyclomatic complexity
- **Modularity** (25%): Fan-in/fan-out balance, god file detection
- **Readability** (25%): Documentation coverage, comment ratio
- **Change Risk** (15%): Complexity-based risk assessment
- **Dependency Hygiene** (10%): Dependency count, circular dependency detection

### 🐛 Code Smell Detection
Detects industry-recognized code smells with supporting metrics:
- **God Files**: Too large, too many responsibilities
- **Long Functions**: Exceeding length thresholds
- **High Cyclomatic Complexity**: Too many decision points
- **Tight Coupling**: High fan-out, too many dependencies
- **Dead/Unused Code**: Symbols not referenced in call graph
- **Orphaned Files**: Isolated, not imported or importing
- **Change Hotspots**: Complex, large, tightly-coupled files

### 🔨 Refactoring Suggestions
Actionable, explainable guidance for each detected smell:
- **Strategy recommendations** (split, extract, decouple, etc.)
- **Step-by-step guidance** with examples
- **Effort and priority** assessment for prioritization
- **Benefits** clearly stated

## Architecture

### Modules

```
code_health/
├── __init__.py              # Package exports
├── stats.py                 # CodeStatistics class
├── health_score.py          # HealthScoreCalculator class
├── smells.py                # CodeSmellDetector class
├── refactoring.py           # RefactoringAdvisor class
├── exporter.py              # AnalysisExporter class
├── visualization.py         # Streamlit UI rendering
└── generate_report.py       # Standalone CLI tool
```

### Core Classes

#### `CodeStatistics`
Computes comprehensive code metrics.

```python
from code_health import CodeStatistics

stats_computer = CodeStatistics(repo_path, call_graph, symbol_table)
stats = stats_computer.compute_all_statistics()
# Returns: {'file_stats': {...}, 'module_stats': {...}, 'repo_stats': {...}}
```

#### `HealthScoreCalculator`
Calculates weighted health score.

```python
from code_health import HealthScoreCalculator

health_calc = HealthScoreCalculator(stats, call_graph, symbol_table)
result = health_calc.calculate_overall_health()
# Returns: {'overall_score': 75.2, 'dimension_scores': {...}, 'interpretation': {...}}
```

#### `CodeSmellDetector`
Detects code smells.

```python
from code_health import CodeSmellDetector

detector = CodeSmellDetector(stats, call_graph, symbol_table, repo_path)
smells = detector.detect_all_smells()
# Returns: List of dicts with type, severity, description, metrics
```

#### `RefactoringAdvisor`
Generates refactoring suggestions.

```python
from code_health import RefactoringAdvisor

advisor = RefactoringAdvisor(smells, stats)
suggestions = advisor.generate_suggestions()
# Returns: List of dicts with strategies, effort, priority, steps
```

#### `AnalysisExporter`
Exports analysis to JSON/Markdown.

```python
from code_health import AnalysisExporter

exporter = AnalysisExporter(output_dir="code_health")
exporter.export_statistics(stats)
exporter.export_health_score(health_result)
exporter.export_smells(smells)
exporter.export_refactoring_suggestions(suggestions)
exporter.export_full_report(health_result, stats, smells, suggestions)
```

## Usage

### Via Streamlit Dashboard

The Code Health & Quality tab is integrated into the main Streamlit app:

```bash
streamlit run retrieval/app.py
```

Then navigate to the **"💪 Code Health & Quality"** tab.

### Standalone CLI

Generate reports without the Streamlit UI:

```bash
python code_health/generate_report.py <repo_path> \
    --call-graph data/MeetMate-AI-Meeting-Assistant/call_graph.json \
    --symbol-table data/MeetMate-AI-Meeting-Assistant/symbol_table.json \
    --output code_health
```

**Output files:**
- `code_health/stats.json` - Code statistics
- `code_health/health_score.json` - Health score details
- `code_health/smells.json` - Detected code smells
- `code_health/refactor_suggestions.md` - Refactoring guidance
- `code_health/CODE_HEALTH_REPORT.md` - Comprehensive report

### Programmatic API

```python
from code_health import (
    CodeStatistics,
    HealthScoreCalculator,
    CodeSmellDetector,
    RefactoringAdvisor,
    AnalysisExporter
)

# Load data
with open('call_graph.json') as f:
    call_graph = json.load(f)
with open('symbol_table.json') as f:
    symbol_table = json.load(f)

# Analyze
stats_computer = CodeStatistics(repo_path, call_graph, symbol_table)
stats = stats_computer.compute_all_statistics()

health_calc = HealthScoreCalculator(stats, call_graph, symbol_table)
health_result = health_calc.calculate_overall_health()

detector = CodeSmellDetector(stats, call_graph, symbol_table, repo_path)
smells = detector.detect_all_smells()

advisor = RefactoringAdvisor(smells, stats)
suggestions = advisor.generate_suggestions()

# Export
exporter = AnalysisExporter()
exporter.export_full_report(health_result, stats, smells, suggestions)
```

## Metrics Reference

### Code Statistics

| Metric | Definition | Unit |
|--------|------------|------|
| LOC | Lines of Code | count |
| Functions | Function definitions | count |
| Classes | Class definitions | count |
| CC | Cyclomatic Complexity | score (1+) |
| Fan-in | Number of callers | count |
| Fan-out | Number of callees | count |
| Docstring Coverage | Documented functions | percentage |
| Comment Ratio | Comments per code line | ratio |

### Health Score Thresholds

| Dimension | Threshold | Ideal |
|-----------|-----------|-------|
| Function Length | 50 lines | 15-30 lines |
| Cyclomatic Complexity | 10-15 | 1-5 |
| Fan-out | 20 | 5-10 |
| Comment Ratio | 0.1 (10%) | 0.15-0.3 (15-30%) |

### Code Smell Severity

- **Critical**: Severe issues requiring immediate attention
- **High**: Significant quality problems
- **Medium**: Moderate concerns
- **Low**: Minor suggestions

## Health Score Interpretation

| Score | Grade | Level | Action |
|-------|-------|-------|--------|
| 80-100 | A | Excellent | Maintain current practices |
| 60-79 | B | Good | Address detected smells |
| 40-59 | C | Fair | Prioritize refactoring |
| 0-39 | D | Poor | Major refactoring needed |

## Design Decisions

1. **Static Analysis Only**: No runtime instrumentation, deterministic results
2. **Graph-Based**: Leverages call graphs for dependency analysis
3. **Modular**: Each component (stats, scoring, detection, advice) is independent
4. **Explainable**: All recommendations include rationale and supporting metrics
5. **Non-Invasive**: No code modifications, advisory only
6. **Reproducible**: Same inputs always produce same outputs

## Limitations

- Simple complexity estimation (no flow analysis)
- Simplified fan-in/fan-out (basic pattern matching)
- Dead code detection based on call graph only
- No cross-repo dependency analysis
- No performance profiling

## Future Enhancements

- Machine learning-based smell detection
- Historical trend analysis (git-based metrics)
- Custom smell definitions
- Integration with linting tools
- Architecture pattern detection
- Technical debt calculation
