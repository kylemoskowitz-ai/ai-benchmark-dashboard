"""FrontierMath Tier 4 benchmark ingestor."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class FrontierMathIngestor(BaseIngestor):
    """Ingestor for FrontierMath Tier 4 benchmark.

    FrontierMath is a collection of challenging mathematical problems.
    Tier 4 represents the most difficult problems, requiring
    graduate-level mathematical reasoning.

    Data source: Epoch AI evaluations
    """

    BENCHMARK_ID = "frontiermath_tier4"

    BENCHMARK_META = Benchmark(
        benchmark_id="frontiermath_tier4",
        name="FrontierMath (Tier 4)",
        category="math",
        description=(
            "FrontierMath Tier 4 contains the most challenging mathematical problems, "
            "requiring graduate-level reasoning. Scores represent percentage of "
            "problems solved correctly."
        ),
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://epoch.ai/frontiermath",
        paper_url="https://arxiv.org/abs/2411.04872",
        notes="Tier 4 = hardest problems. Most models score <15%.",
    )

    SNAPSHOT_PATHS = [
        Path("frontiermath_tier_4.csv"),
        Path("data/snapshots/frontiermath_tier_4.csv"),
    ]

    def fetch_raw(self) -> Path:
        """Load FrontierMath data from local CSV snapshot."""
        # Get project root (this file is at src/ingestors/frontier_math.py)
        project_root = Path(__file__).parent.parent.parent

        for rel_path in self.SNAPSHOT_PATHS:
            snapshot_path = project_root / rel_path
            if snapshot_path.exists():
                return snapshot_path

        raise FileNotFoundError(
            f"FrontierMath snapshot not found in {project_root}. Tried: {self.SNAPSHOT_PATHS}"
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse FrontierMath CSV into Result objects."""
        df = pl.read_csv(raw_path)

        # Create source record
        source = Source(
            source_id=self.generate_source_id("https://epoch.ai/frontiermath"),
            source_type=SourceType.THIRD_PARTY_LEADERBOARD,
            source_title="Epoch AI FrontierMath Evaluations",
            source_url="https://epoch.ai/frontiermath",
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
            notes="Epoch AI's standardized evaluations on FrontierMath Tier 4",
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
                    },
                )
                self.register_model(model)

                # Parse score (convert from 0-1 to percentage)
                raw_score = self._parse_float(row.get("Best score (across scorers)"))
                if raw_score is not None:
                    score = raw_score * 100 if raw_score <= 1 else raw_score
                else:
                    score = None

                stderr = self._parse_float(row.get("stderr"))
                if stderr is not None and stderr <= 1:
                    stderr = stderr * 100

                eval_date = self.parse_date(row.get("Started at"))

                result = Result(
                    result_id=self.generate_result_id(model_id, eval_date or release_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    score_stderr=stderr,
                    evaluation_date=eval_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.B,  # Epoch AI = semi-official
                    evaluation_notes=f"Epoch AI evaluation. ID: {row.get('id', 'N/A')}",
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
            "gpt-4": ["gpt-4"],
            "o1": ["o1-"],
            "o3": ["o3-"],
            "claude-3.5": ["claude-3-5", "sonnet-3.5"],
            "claude-4": ["sonnet-4", "claude-4"],
            "gemini-2": ["gemini-2"],
            "gemini-2.5": ["gemini-2.5", "deep-think"],
            "grok-3": ["grok-3"],
            "deepseek": ["deepseek"],
            "qwen": ["qwen"],
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
