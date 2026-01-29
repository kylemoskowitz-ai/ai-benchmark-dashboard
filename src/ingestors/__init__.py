"""Benchmark data ingestors."""

from .base import BaseIngestor
from .swe_bench import SWEBenchIngestor
from .metr import METRIngestor
from .frontier_math import FrontierMathIngestor
from .epoch import EpochIngestor

# Registry of all available ingestors
INGESTORS: dict[str, type[BaseIngestor]] = {
    "swe_bench_verified": SWEBenchIngestor,
    "metr_time_horizons": METRIngestor,
    "frontiermath_tier4": FrontierMathIngestor,
    # "epoch": EpochIngestor,  # Generic template - use for custom benchmarks
    # TODO: Add more ingestors
    # "arc_agi": ARCAGIIngestor,
}


def get_ingestor(benchmark_id: str) -> BaseIngestor:
    """Get an ingestor instance by benchmark ID."""
    if benchmark_id not in INGESTORS:
        raise ValueError(f"Unknown benchmark: {benchmark_id}. Available: {list(INGESTORS.keys())}")
    return INGESTORS[benchmark_id]()


def get_all_ingestors() -> list[BaseIngestor]:
    """Get instances of all registered ingestors."""
    return [cls() for cls in INGESTORS.values()]


__all__ = [
    "BaseIngestor",
    "SWEBenchIngestor",
    "METRIngestor",
    "FrontierMathIngestor",
    "EpochIngestor",
    "INGESTORS",
    "get_ingestor",
    "get_all_ingestors",
]
