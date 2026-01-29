"""Database layer for benchmark data."""

from .connection import get_connection, init_database
from .queries import (
    get_all_benchmarks,
    get_all_models,
    get_results_for_benchmark,
    get_results_for_model,
    get_frontier_results,
    get_data_quality_summary,
    insert_results,
    insert_source,
    insert_model,
)

__all__ = [
    "get_connection",
    "init_database",
    "get_all_benchmarks",
    "get_all_models",
    "get_results_for_benchmark",
    "get_results_for_model",
    "get_frontier_results",
    "get_data_quality_summary",
    "insert_results",
    "insert_source",
    "insert_model",
]
