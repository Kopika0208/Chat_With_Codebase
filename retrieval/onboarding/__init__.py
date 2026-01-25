"""
Onboarding module for codebase understanding.
Provides tools for new developers to learn and navigate a codebase.
"""

from onboarding.analyzer import CodebaseAnalyzer
from onboarding.visualization import (
    render_project_overview,
    render_entry_exit_points,
    render_roadmap,
    render_file_tree,
    render_navigation_hints,
    render_weak_documentation_section,
    render_summary,
)

__all__ = [
    "CodebaseAnalyzer",
    "render_project_overview",
    "render_entry_exit_points",
    "render_roadmap",
    "render_file_tree",
    "render_navigation_hints",
    "render_weak_documentation_section",
    "render_summary",
]
