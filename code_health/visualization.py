"""
Streamlit visualization for Code Health & Quality analysis.
"""

import streamlit as st
import json
import pandas as pd
from typing import Dict, List
from code_health import CodeStatistics, HealthScoreCalculator, CodeSmellDetector, RefactoringAdvisor


def render_code_health_tab(repo_path: str, call_graph: Dict, symbol_table: Dict) -> None:
    """Render the Code Health & Quality tab."""
    
    st.markdown("## Code Health & Quality Analysis")
    
    # Initialize and compute analysis
    with st.spinner("Analyzing code health..."):
        try:
            # Debug: Log input structure
            print(f"[DEBUG] Input symbol_table type: {type(symbol_table)}")
            print(f"[DEBUG] Input symbol_table keys: {list(symbol_table.keys()) if isinstance(symbol_table, dict) else 'NOT A DICT'}")
            
            # Validate and normalize symbol table
            normalized_symbol_table = _normalize_symbol_table(symbol_table)
            
            # Debug: Log normalized structure
            print(f"[DEBUG] Normalized symbol_table type: {type(normalized_symbol_table)}")
            print(f"[DEBUG] Normalized symbol_table keys count: {len(normalized_symbol_table) if isinstance(normalized_symbol_table, dict) else 'NOT A DICT'}")
            
            # Validate call graph
            if not isinstance(call_graph, dict):
                call_graph = {}
            
            # Compute statistics
            stats_computer = CodeStatistics(repo_path, call_graph, normalized_symbol_table)
            stats = stats_computer.compute_all_statistics()
            
            # Ensure repo_stats is valid before proceeding
            repo_stats = stats.get('repo_stats', {})
            if not repo_stats or not isinstance(repo_stats, dict):
                st.error("[ERROR] Unable to compute code statistics. Repository may be empty or invalid.")
                return
            
            # Calculate health score
            health_calculator = HealthScoreCalculator(stats, call_graph, normalized_symbol_table)
            health_result = health_calculator.calculate_overall_health()
            file_scores = health_calculator.calculate_file_scores()
            
            # Detect smells
            smell_detector = CodeSmellDetector(stats, call_graph, normalized_symbol_table, repo_path)
            smells = smell_detector.detect_all_smells()
            
            # Generate refactoring suggestions
            advisor = RefactoringAdvisor(smells, stats)
            suggestions = advisor.generate_suggestions()
            
        except Exception as e:
            st.error(f"[ERROR] Error during analysis: {e}")
            import traceback
            st.write(traceback.format_exc())
            return
    
    # ============================================================
    # OVERALL HEALTH SCORE
    # ============================================================
    st.divider()
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        overall_score = float(health_result.get('overall_score', 0))
        grade = health_result.get('interpretation', {}).get('grade', 'N/A')
        level = health_result.get('interpretation', {}).get('level', 'Unknown')
        
        # Color-coded score display
        if overall_score >= 80:
            color = "[GREEN]"
        elif overall_score >= 60:
            color = "[YELLOW]"
        elif overall_score >= 40:
            color = "[ORANGE]"
        else:
            color = "[RED]"
        
        st.metric(
            "Overall Code Health Score",
            f"{overall_score:.1f}/100",
            delta=f"Grade {grade}",
        )
        st.markdown(f"**Status:** {color} {level}")
        st.info(health_result.get('interpretation', {}).get('description', 'N/A'))
    
    with col2:
        st.metric("Detected Issues", int(len(smells)))
    
    with col3:
        st.metric("Refactoring Suggestions", int(len(suggestions)))
    
    # ============================================================
    # DIMENSION SCORES
    # ============================================================
    st.divider()
    st.markdown("### 📊 Health Dimensions")
    
    dimension_data = []
    for dim, score in health_result['dimension_scores'].items():
        dimension_data.append({
            'Dimension': dim.replace('_', ' ').title(),
            'Score': score,
        })
    
    df_dimensions = pd.DataFrame(dimension_data)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Bar chart
        st.bar_chart(df_dimensions.set_index('Dimension')['Score'])
    
    with col2:
        # Table
        st.dataframe(df_dimensions, width='stretch', hide_index=True)
    
    # ============================================================
    # CODE STATISTICS
    # ============================================================
    st.divider()
    st.markdown("### 📈 Code Statistics")
    
    repo_stats = stats.get('repo_stats', {})
    
    metrics_cols = st.columns(4)
    
    with metrics_cols[0]:
        st.metric("Total Files", int(repo_stats.get('num_files', 0)))
    
    with metrics_cols[1]:
        st.metric("Total LOC", int(repo_stats.get('total_loc', 0)))
    
    with metrics_cols[2]:
        st.metric("Functions", int(repo_stats.get('num_functions', 0)))
    
    with metrics_cols[3]:
        st.metric("Classes", int(repo_stats.get('num_classes', 0)))
    
    # Detailed statistics table
    st.markdown("#### Repository-Level Metrics")
    
    detailed_stats = {
        'Metric': [
            'Lines of Code (Code)',
            'Lines of Code (Comments)',
            'Blank Lines',
            'Comment-to-Code Ratio',
            'Avg Function Length',
            'Avg Class Size',
            'Avg Cyclomatic Complexity',
            'Modules',
        ],
        'Value': [
            f"{int(repo_stats.get('total_loc_code', 0))}",
            f"{int(repo_stats.get('total_loc_comment', 0))}",
            f"{int(repo_stats.get('loc_blank', 0))}",
            f"{repo_stats.get('comment_to_code_ratio', 0):.2f}",
            f"{repo_stats.get('avg_function_length', 0):.1f}",
            f"{repo_stats.get('avg_class_size', 0):.1f}",
            f"{repo_stats.get('avg_cyclomatic_complexity', 0):.2f}",
            f"{int(repo_stats.get('num_modules', 0))}",
        ],
    }
    
    st.dataframe(pd.DataFrame(detailed_stats), width='stretch', hide_index=True)
    
    # Module-level statistics
    if stats.get('module_stats'):
        st.markdown("#### Module-Level Breakdown")
        
        module_data = []
        for module, mod_stats in stats['module_stats'].items():
            module_data.append({
                'Module': module,
                'Files': int(mod_stats['num_files']),
                'LOC': int(mod_stats['loc']),
                'Functions': int(mod_stats['num_functions']),
                'Classes': int(mod_stats['num_classes']),
                'Avg CC': f"{mod_stats['avg_cyclomatic_complexity']:.2f}",
            })
        
        st.dataframe(pd.DataFrame(module_data), width='stretch', hide_index=True)
    
    # ============================================================
    # CODE SMELLS
    # ============================================================
    st.divider()
    st.markdown("### 🐛 Detected Code Smells")
    
    if smells:
        # Group smells by type
        smells_by_type = {}
        for smell in smells:
            smell_type = smell['type']
            if smell_type not in smells_by_type:
                smells_by_type[smell_type] = []
            smells_by_type[smell_type].append(smell)
        
        # Create expandable sections for each smell type
        for smell_type in sorted(smells_by_type.keys()):
            type_smells = smells_by_type[smell_type]
            
            with st.expander(f"{smell_type} ({len(type_smells)})"):
                for i, smell in enumerate(type_smells, 1):
                    st.markdown(f"**#{i}** {smell.get('file', 'Unknown')}")
                    
                    # Severity badge
                    severity = smell.get('severity', 'medium').upper()
                    if severity == 'CRITICAL':
                        st.error("[CRITICAL] Severity: " + severity)
                    elif severity == 'HIGH':
                        st.warning("[WARNING] Severity: " + severity)
                    elif severity == 'MEDIUM':
                        st.info(f"ℹ️ Severity: {severity}")
                    else:
                        st.success("[OK] Severity: " + severity)
                    
                    st.markdown(f"**Description:** {smell.get('description', 'N/A')}")
                    
                    if smell.get('why_problem'):
                        st.markdown(f"**Why it's a problem:** {smell['why_problem']}")
                    
                    # Metrics
                    if smell.get('metrics'):
                        st.markdown("**Metrics:**")
                        metrics_cols = st.columns(len(smell['metrics']))
                        for col, (metric_name, metric_value) in zip(metrics_cols, smell['metrics'].items()):
                            with col:
                                if isinstance(metric_value, (int, float)):
                                    st.metric(
                                        metric_name.replace('_', ' ').title(),
                                        f"{metric_value:.1f}" if isinstance(metric_value, float) else int(metric_value)
                                    )
                                else:
                                    st.markdown(f"**{metric_name.replace('_', ' ').title()}:** {metric_value}")
                    
                    st.divider()
    else:
        st.success("✅ No code smells detected!")
    
    # ============================================================
    # HIGH-RISK FILES
    # ============================================================
    st.divider()
    st.markdown("### 🚨 High-Risk Files")
    
    # Sort files by score (lowest first)
    high_risk_files = sorted(
        file_scores.items(),
        key=lambda x: x[1]['score']
    )[:10]
    
    if high_risk_files:
        risk_data = []
        for file_path, scores in high_risk_files:
            risk_data.append({
                'File': file_path,
                'Health Score': f"{scores['score']:.1f}",
                'Complexity': f"{scores['complexity']:.1f}",
                'LOC': int(scores['loc']),
                'Doc Coverage': f"{scores['docstring_coverage']:.0f}%",
            })
        
        st.dataframe(pd.DataFrame(risk_data), width='stretch', hide_index=True)
    else:
        st.success("✅ No high-risk files identified!")
    
    # ============================================================
    # REFACTORING SUGGESTIONS
    # ============================================================
    st.divider()
    st.markdown("### 🔨 Refactoring Suggestions")
    
    if suggestions:
        # Sort by priority
        for i, suggestion in enumerate(suggestions, 1):
            smell_type = suggestion['smell_type']
            file = suggestion['file']
            priority = suggestion['priority'].upper()
            effort = suggestion['effort'].upper()
            
            with st.expander(f"#{i} {smell_type} — {file}"):
                # Header info
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    priority_color = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(priority, '⚪')
                    st.markdown(f"**Priority:** {priority_color} {priority}")
                
                with col2:
                    effort_color = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(effort, '⚪')
                    st.markdown(f"**Effort:** {effort_color} {effort}")
                
                with col3:
                    st.markdown(f"**Impact:** {suggestion.get('rationale', 'N/A')[:50]}...")
                
                st.divider()
                
                # Description
                if suggestion.get('description'):
                    st.markdown(f"**Problem:** {suggestion['description']}")
                
                st.markdown(f"**Rationale:** {suggestion.get('rationale', 'N/A')}")
                
                # Strategies
                strategies = suggestion.get('strategies', [])
                if strategies:
                    st.markdown("#### Suggested Strategies:")
                    
                    for strategy in strategies:
                        with st.expander(f"📍 {strategy['name']}"):
                            st.markdown(f"**Description:** {strategy['description']}")
                            
                            st.markdown("**Steps:**")
                            for step in strategy.get('steps', []):
                                st.markdown(f"- {step}")
                            
                            if strategy.get('benefit'):
                                st.markdown(f"**Benefit:** {strategy['benefit']}")
    else:
        st.success("✅ No refactoring suggestions at this time!")
    
    # ============================================================
    # EXPORT OPTIONS
    # ============================================================
    st.divider()
    st.markdown("### 📥 Export Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export as JSON
        export_data = {
            'overall_health': health_result,
            'statistics': {
                'repository': repo_stats,
                'modules': stats.get('module_stats', {}),
            },
            'code_smells': smells,
            'refactoring_suggestions': suggestions,
            'file_scores': {k: v for k, v in file_scores.items()},
        }
        
        json_str = json.dumps(export_data, indent=2, default=str)
        st.download_button(
            label="📊 Download JSON",
            data=json_str,
            file_name="code_health_analysis.json",
            mime="application/json",
        )
    
    with col2:
        # Export as CSV (statistics)
        csv_data = pd.DataFrame(detailed_stats).to_csv(index=False)
        st.download_button(
            label="📈 Download Stats (CSV)",
            data=csv_data,
            file_name="code_statistics.csv",
            mime="text/csv",
        )
    
    with col3:
        # Export file scores as CSV
        file_scores_df = pd.DataFrame(
            [{'File': k, **v} for k, v in file_scores.items()]
        )
        csv_scores = file_scores_df.to_csv(index=False)
        st.download_button(
            label="📋 Download File Scores (CSV)",
            data=csv_scores,
            file_name="file_scores.csv",
            mime="text/csv",
        )


def _normalize_symbol_table(symbol_table: Dict) -> Dict:
    """
    Normalize symbol table to flat dict format.
    Handles both flat and nested formats.
    Extremely defensive against malformed data.
    
    Args:
        symbol_table: Symbol table (may have 'global_index', 'file_symbols' keys)
    
    Returns:
        Normalized flat dictionary
    """
    try:
        if not symbol_table:
            return {}
        
        # Ensure it's a dict
        if not isinstance(symbol_table, dict):
            return {}
        
        # Get the keys for inspection
        keys = list(symbol_table.keys()) if symbol_table else []
        
        # Already flat format (no global_index or file_symbols keys)
        if 'global_index' not in keys and 'file_symbols' not in keys:
            # This is already a flat symbol table
            # Validate that it contains valid entries
            result = {}
            for k, v in symbol_table.items():
                if isinstance(k, str) and isinstance(v, dict):
                    result[k] = v
            return result if result else {}
        
        # Nested format - extract global symbols
        flattened = {}
        
        if 'global_index' in symbol_table:
            global_index = symbol_table.get('global_index', {})
            if not isinstance(global_index, dict):
                return {}
            
            global_symbols = global_index.get('global_symbols', {})
            
            if not isinstance(global_symbols, dict):
                return {}
            
            for symbol_name, occurrences in global_symbols.items():
                try:
                    if isinstance(symbol_name, str):
                        if isinstance(occurrences, list) and len(occurrences) > 0:
                            first_occ = occurrences[0]
                            if isinstance(first_occ, dict):
                                flattened[symbol_name] = {
                                    'name': symbol_name,
                                    'type': 'function' if first_occ.get('kind') == 'function' else 'class',
                                }
                        elif isinstance(occurrences, dict):
                            flattened[symbol_name] = {
                                'name': symbol_name,
                                'type': 'function' if occurrences.get('kind') == 'function' else 'class',
                            }
                except (KeyError, TypeError, AttributeError):
                    continue
        
        return flattened if flattened else {}
    
    except Exception as e:
        print(f"⚠️ Error normalizing symbol table: {e}")
        return {}
