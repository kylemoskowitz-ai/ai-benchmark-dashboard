"""METR Time Horizons benchmark ingestor."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from .epoch_fetcher import get_epoch_csv
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class METRIngestor(BaseIngestor):
    """Ingestor for METR Time Horizons benchmark.

    METR evaluates AI models on their ability to complete long-horizon
    autonomous tasks. The "time horizon" metric indicates the task
    complexity (in hours) that a model can reliably complete.

    Data source: Epoch AI (automatically downloaded from epoch.ai)
    """

    BENCHMARK_ID = "metr_time_horizons"

    BENCHMARK_META = Benchmark(
        benchmark_id="metr_time_horizons",
        name="METR Time Horizons",
        category="agentic",
        description=(
            "METR evaluates AI agents on long-horizon autonomous tasks. "
            "The P50 time horizon (in minutes) indicates the median task complexity "
            "a model can complete autonomously."
        ),
        unit="minutes",
        scale_min=0.0,
        scale_max=1000.0,  # Time horizons can be high
        higher_is_better=True,
        official_url="https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/",
        paper_url="https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/",
        notes="P50 time horizon in minutes. Higher = can complete more complex autonomous tasks. Data from METR-Horizon-v1.1.",
    )

    def fetch_raw(self) -> Path:
        """Fetch METR data from curated snapshot.

        Uses the latest METR-Horizon-v1.1 data from metr.org.
        """
        # Use curated snapshot with v1.1 data
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "metr_time_horizons.csv"
        if snapshot_path.exists():
            return snapshot_path

        # Fallback to Epoch data (older version)
        return get_epoch_csv("metr_time_horizons_external.csv")

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse METR CSV into Result objects."""
        df = pl.read_csv(raw_path)

        # Create source record
        source = Source(
            source_id=self.generate_source_id("https://metr.org/time-horizons-v1.1"),
            source_type=SourceType.OFFICIAL_PAPER,
            source_title="METR Time Horizons v1.1",
            source_url="https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/",
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
            notes="METR-Horizon-v1.1 benchmark results. P50 time horizon in minutes.",
        )
        self.register_source(source)

        results = []
        for row in df.iter_rows(named=True):
            try:
                # Handle both snapshot format and Epoch format
                model_name = row.get("model") or row.get("Model version", "")
                if not model_name:
                    continue

                provider = row.get("provider") or row.get("Organization", "Unknown")
                release_date = self.parse_date(row.get("date") or row.get("Release date"))

                # Create/register model
                model_id = self.normalize_model_id(model_name, provider)
                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    release_date=release_date,
                    status=ModelStatus.VERIFIED,
                )
                self.register_model(model)

                # Parse time horizon score (P50 in minutes)
                time_horizon = self._parse_float(row.get("score") or row.get("Time horizon"))

                # Parse confidence intervals
                ci_low = self._parse_float(row.get("score_ci_low") or row.get("CI_low"))
                ci_high = self._parse_float(row.get("score_ci_high") or row.get("CI_high"))

                # Additional score metrics
                avg_score = self._parse_float(row.get("avg_score") or row.get("average_score"))

                if time_horizon is None:
                    continue

                # Create result
                result = Result(
                    result_id=self.generate_result_id(model_id, release_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=time_horizon,
                    score_ci_low=ci_low,
                    score_ci_high=ci_high,
                    evaluation_date=release_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,  # METR = official
                    evaluation_notes=(
                        f"P50 time horizon: {time_horizon} min. "
                        f"Avg task score: {avg_score}. "
                        f"Notes: {row.get('notes', 'N/A')}"
                    ),
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")
                continue

        return results

    def _infer_family(self, model_name: str) -> str | None:
        """Infer model family from name."""
        name_lower = model_name.lower()

        families = {
            "gpt-4": ["gpt-4", "gpt4"],
            "o1": ["o1-"],
            "claude-3": ["claude-3"],
            "claude-3.5": ["claude-3-5", "claude-3.5"],
            "gemini": ["gemini"],
            "grok": ["grok"],
            "llama": ["llama"],
            "deepseek": ["deepseek"],
        }

        for family, patterns in families.items():
            for pattern in patterns:
                if pattern in name_lower:
                    return family

        return None

    def _parse_float(self, value: any) -> float | None:
        """Safely parse a float value."""
        if value is None or value == "" or value == "None":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
