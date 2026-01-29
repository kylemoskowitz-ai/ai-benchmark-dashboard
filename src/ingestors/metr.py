"""METR Time Horizons benchmark ingestor."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class METRIngestor(BaseIngestor):
    """Ingestor for METR Time Horizons benchmark.

    METR evaluates AI models on their ability to complete long-horizon
    autonomous tasks. The "time horizon" metric indicates the task
    complexity (in hours) that a model can reliably complete.

    Data source: METR reports and Epoch AI evaluations
    """

    BENCHMARK_ID = "metr_time_horizons"

    BENCHMARK_META = Benchmark(
        benchmark_id="metr_time_horizons",
        name="METR Time Horizons",
        category="agentic",
        description=(
            "METR evaluates AI agents on long-horizon autonomous tasks. "
            "The time horizon metric indicates task complexity the model can complete."
        ),
        unit="hours",
        scale_min=0.0,
        scale_max=1000.0,  # Time horizons can be high
        higher_is_better=True,
        official_url="https://metr.org/",
        paper_url="https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/",
        notes="Time horizon in hours. Higher = can complete more complex autonomous tasks.",
    )

    SNAPSHOT_PATHS = [
        Path("metr_time_horizons_external.csv"),
        Path("data/snapshots/metr_time_horizons_external.csv"),
    ]

    def fetch_raw(self) -> Path:
        """Load METR data from local CSV snapshot."""
        # Get project root (this file is at src/ingestors/metr.py)
        project_root = Path(__file__).parent.parent.parent

        for rel_path in self.SNAPSHOT_PATHS:
            snapshot_path = project_root / rel_path
            if snapshot_path.exists():
                return snapshot_path

        raise FileNotFoundError(
            f"METR snapshot not found in {project_root}. Tried: {self.SNAPSHOT_PATHS}"
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse METR CSV into Result objects."""
        df = pl.read_csv(raw_path)

        # Create source record
        source = Source(
            source_id=self.generate_source_id("https://metr.org/time-horizons"),
            source_type=SourceType.OFFICIAL_PAPER,
            source_title="METR Time Horizons Report",
            source_url="https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/",
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
            notes="METR's evaluation of AI agent time horizons",
        )
        self.register_source(source)

        results = []
        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("Model version", "")
                if not model_name:
                    continue

                provider = row.get("Organization", "Unknown")
                release_date = self.parse_date(row.get("Release date"))

                # Create/register model
                model_id = self.normalize_model_id(model_name, provider)
                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    release_date=release_date,
                    status=ModelStatus.VERIFIED,
                    training_compute_flop=self._parse_float(row.get("Training compute (FLOP)")),
                    training_compute_notes=row.get("Training compute notes"),
                    metadata={
                        "country": row.get("Country", ""),
                        "source_link": row.get("Source link", ""),
                    },
                )
                self.register_model(model)

                # Parse time horizon score
                time_horizon = self._parse_float(row.get("Time horizon"))

                # Parse confidence intervals
                ci_low = self._parse_float(row.get("CI_low"))
                ci_high = self._parse_float(row.get("CI_high"))

                # Additional score metrics
                avg_score = self._parse_float(row.get("average_score"))

                # Create result
                result = Result(
                    result_id=self.generate_result_id(model_id, release_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=time_horizon,
                    score_ci_low=ci_low,
                    score_ci_high=ci_high,
                    evaluation_date=release_date,  # Use release date as proxy
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,  # METR = official
                    evaluation_notes=(
                        f"Time horizon: {time_horizon}h. "
                        f"Avg task score: {avg_score}. "
                        f"Notes: {row.get('Notes', 'N/A')}"
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
