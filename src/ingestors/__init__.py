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
# Priority: Official sources first, then third-party
INGESTORS: dict[str, type[BaseIngestor]] = {
    "swe_bench_verified": SWEBenchOfficialIngestor,  # Official leaderboard (Tier A)
    "swe_bench_epoch": SWEBenchIngestor,  # Epoch AI fallback (Tier B)
    "metr_time_horizons": METRIngestor,
    "frontiermath_tier4": FrontierMathIngestor,
    "arc_agi_1": ARCAGI1Ingestor,
    "arc_agi_2": ARCAGI2Ingestor,
    "mmmu": MMMUIngestor,
    "zerobench": ZeroBenchIngestor,
    "humanities_last_exam": HumanitiesLastExamIngestor,
    "remote_labor_index": RemoteLaborIndexIngestor,
    "epoch_capabilities_index": EpochCapabilitiesIndexIngestor,
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
