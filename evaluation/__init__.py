"""Evaluation module for automatic metrics collection during pipeline execution.

No ground truth evaluation, no manual intervention. Just raw metric collection.
"""

from .collector import (
    save_ingestion_metrics,
    save_retrieval_metrics,
    save_code_health_metrics,
    save_contribution_metrics,
    save_graph_metrics,
    load_evaluation_summary,
)

__all__ = [
    "save_ingestion_metrics",
    "save_retrieval_metrics",
    "save_code_health_metrics",
    "save_contribution_metrics",
    "save_graph_metrics",
    "load_evaluation_summary",
]
