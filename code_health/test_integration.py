"""
Integration test for Code Health module.
Verifies all components work together correctly.
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add parent directory to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)


def test_code_health_integration():
    """Test complete code health analysis pipeline."""
    
    print("🧪 Testing Code Health Integration...")
    print("-" * 60)
    
    # Test imports
    try:
        from code_health import (
            CodeStatistics,
            HealthScoreCalculator,
            CodeSmellDetector,
            RefactoringAdvisor,
            AnalysisExporter,
        )
        print("✓ All modules imported successfully")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    
    # Create test data
    test_repo_path = os.path.join(PROJECT_ROOT, "retrieval")
    
    if not os.path.isdir(test_repo_path):
        print(f"⚠️ Test repo path not found: {test_repo_path}")
        print("   Using mock data for testing...")
        
        test_stats = {
            'repo_stats': {
                'num_files': 10,
                'total_loc': 5000,
                'total_loc_code': 4000,
                'total_loc_comment': 500,
                'loc_blank': 500,
                'num_functions': 100,
                'num_classes': 20,
                'avg_function_length': 30,
                'avg_class_size': 250,
                'comment_to_code_ratio': 0.125,
                'avg_cyclomatic_complexity': 5.5,
                'num_modules': 5,
            },
            'file_stats': {
                'test.py': {
                    'loc': 500,
                    'loc_code': 400,
                    'loc_comment': 50,
                    'loc_blank': 50,
                    'num_functions': 10,
                    'num_classes': 2,
                    'cyclomatic_complexity': 8,
                    'average_function_length': 35,
                    'docstring_coverage': 70,
                    'fan_in': 3,
                    'fan_out': 5,
                    'dependency_count': 5,
                },
            },
            'module_stats': {
                'retrieval': {
                    'num_files': 10,
                    'loc': 5000,
                    'loc_code': 4000,
                    'num_functions': 100,
                    'num_classes': 20,
                    'avg_cyclomatic_complexity': 5.5,
                    'avg_function_length': 30,
                },
            },
        }
        
        test_call_graph = {
            'function_a': ['function_b', 'function_c'],
            'function_b': ['function_c'],
            'function_c': [],
        }
        
        test_symbol_table = {
            'function_a': {'type': 'function'},
            'function_b': {'type': 'function'},
            'function_c': {'type': 'function'},
        }
    else:
        print(f"✓ Using test repository: {test_repo_path}")
        
        # Compute statistics
        try:
            print("\n📊 Computing statistics...")
            stats_computer = CodeStatistics(test_repo_path, {}, {})
            test_stats = stats_computer.compute_all_statistics()
            print(f"✓ Computed statistics for {len(test_stats['file_stats'])} files")
        except Exception as e:
            print(f"✗ Error computing statistics: {e}")
            return False
        
        test_call_graph = {}
        test_symbol_table = {}
    
    # Test HealthScoreCalculator
    try:
        print("\n💪 Testing HealthScoreCalculator...")
        health_calc = HealthScoreCalculator(test_stats, test_call_graph, test_symbol_table)
        health_result = health_calc.calculate_overall_health()
        
        assert 'overall_score' in health_result, "Missing overall_score"
        assert 0 <= health_result['overall_score'] <= 100, "Score out of range"
        assert 'dimension_scores' in health_result, "Missing dimension_scores"
        assert 'interpretation' in health_result, "Missing interpretation"
        
        print(f"✓ Health Score: {health_result['overall_score']:.1f}/100")
        print(f"  Grade: {health_result['interpretation']['grade']}")
        
        file_scores = health_calc.calculate_file_scores()
        print(f"✓ Calculated file scores for {len(file_scores)} files")
        
    except AssertionError as e:
        print(f"✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error in HealthScoreCalculator: {e}")
        return False
    
    # Test CodeSmellDetector
    try:
        print("\n🐛 Testing CodeSmellDetector...")
        detector = CodeSmellDetector(test_stats, test_call_graph, test_symbol_table, test_repo_path)
        smells = detector.detect_all_smells()
        
        assert isinstance(smells, list), "Smells should be a list"
        print(f"✓ Detected {len(smells)} code smell(s)")
        
        if smells:
            smell = smells[0]
            assert 'type' in smell, "Missing smell type"
            assert 'file' in smell, "Missing file"
            assert 'severity' in smell, "Missing severity"
            assert 'description' in smell, "Missing description"
            print(f"✓ First smell: {smell['type']} (severity: {smell['severity']})")
        
    except AssertionError as e:
        print(f"✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error in CodeSmellDetector: {e}")
        return False
    
    # Test RefactoringAdvisor
    try:
        print("\n🔨 Testing RefactoringAdvisor...")
        advisor = RefactoringAdvisor(smells, test_stats)
        suggestions = advisor.generate_suggestions()
        
        assert isinstance(suggestions, list), "Suggestions should be a list"
        print(f"✓ Generated {len(suggestions)} suggestion(s)")
        
        if suggestions:
            suggestion = suggestions[0]
            assert 'smell_type' in suggestion, "Missing smell_type"
            assert 'file' in suggestion, "Missing file"
            assert 'effort' in suggestion, "Missing effort"
            assert 'priority' in suggestion, "Missing priority"
            assert 'strategies' in suggestion, "Missing strategies"
            print(f"✓ First suggestion: {suggestion['smell_type']} "
                  f"(Priority: {suggestion['priority']}, Effort: {suggestion['effort']})")
        
    except AssertionError as e:
        print(f"✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error in RefactoringAdvisor: {e}")
        return False
    
    # Test AnalysisExporter
    try:
        print("\n💾 Testing AnalysisExporter...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = AnalysisExporter(tmpdir)
            
            stats_file = exporter.export_statistics(test_stats)
            assert os.path.exists(stats_file), f"Stats file not created: {stats_file}"
            print(f"✓ Exported statistics")
            
            health_file = exporter.export_health_score(health_result)
            assert os.path.exists(health_file), f"Health file not created: {health_file}"
            print(f"✓ Exported health score")
            
            smells_file = exporter.export_smells(smells)
            assert os.path.exists(smells_file), f"Smells file not created: {smells_file}"
            print(f"✓ Exported code smells")
            
            suggestions_file = exporter.export_refactoring_suggestions(suggestions)
            assert os.path.exists(suggestions_file), f"Suggestions file not created: {suggestions_file}"
            print(f"✓ Exported refactoring suggestions")
            
            report_file = exporter.export_full_report(health_result, test_stats, smells, suggestions)
            assert os.path.exists(report_file), f"Report file not created: {report_file}"
            print(f"✓ Exported full report")
            
            # Verify JSON files are valid
            with open(stats_file) as f:
                json.load(f)
            with open(health_file) as f:
                json.load(f)
            with open(smells_file) as f:
                json.load(f)
            
            print("✓ All JSON files are valid")
        
    except AssertionError as e:
        print(f"✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error in AnalysisExporter: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ All integration tests passed!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_code_health_integration()
    sys.exit(0 if success else 1)
