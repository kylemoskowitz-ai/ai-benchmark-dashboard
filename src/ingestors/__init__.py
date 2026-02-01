"""Benchmark data ingestors."""

from .base import BaseIngestor
from .swe_bench import SWEBenchIngestor
from .swe_bench_official import SWEBenchOfficialIngestor
from .metr import METRIngestor
from .frontier_math import FrontierMathIngestor
from .epoch import EpochIngestor
from .arc_agi import ARCAGI1Ingestor, ARCAGI2Ingestor
from .mmmu import MMMUIngestor
from .zerobench import ZeroBenchIngestor
from .humanities_last_exam import HumanitiesLastExamIngestor
from .remote_labor_index import RemoteLaborIndexIngestor
from .epoch_capabilities_index import EpochCapabilitiesIndexIngestor

# Registry of all available ingestors
# These use automated data fetching from Epoch AI or web scrapers
INGESTORS: dict[str, type[BaseIngestor]] = {
    # Epoch AI sourced (auto-downloaded from epoch.ai/data/benchmark_data.zip)
    "swe_bench_verified": SWEBenchIngestor,  # Epoch AI data
    "metr_time_horizons": METRIngestor,  # Epoch AI data
    "frontiermath_tier4": FrontierMathIngestor,  # Epoch AI data
    "arc_agi_1": ARCAGI1Ingestor,  # Epoch AI data
    "arc_agi_2": ARCAGI2Ingestor,  # Epoch AI data
    "epoch_capabilities_index": EpochCapabilitiesIndexIngestor,  # Epoch AI data
    # Web scraped sources
    "zerobench": ZeroBenchIngestor,  # Scrapes zerobench.github.io
    "humanities_last_exam": HumanitiesLastExamIngestor,  # Scrapes scale.com
    "remote_labor_index": RemoteLaborIndexIngestor,  # Scrapes scale.com
    "mmmu": MMMUIngestor,  # Scrapes vals.ai
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
    "SWEBenchOfficialIngestor",
    "METRIngestor",
    "FrontierMathIngestor",
    "EpochIngestor",
    "ARCAGI1Ingestor",
    "ARCAGI2Ingestor",
    "MMMUIngestor",
    "ZeroBenchIngestor",
    "HumanitiesLastExamIngestor",
    "RemoteLaborIndexIngestor",
    "EpochCapabilitiesIndexIngestor",
    "INGESTORS",
    "get_ingestor",
    "get_all_ingestors",
]
