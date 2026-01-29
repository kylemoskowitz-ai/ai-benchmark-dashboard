"""Generic Epoch AI benchmark ingestor.

This ingestor handles multiple benchmark CSVs from Epoch AI's
standardized evaluation format.
"""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class EpochIngestor(BaseIngestor):
    """Generic ingestor for Epoch AI benchmark data.

    This can ingest any CSV following Epoch AI's standard format:
    - Model version
    - Best score (across scorers)
    - Release date
    - Organization
    - etc.

    Use this as a template for adding new Epoch-format benchmarks.
    """

    BENCHMARK_ID = "epoch_generic"

    # Can be overridden for specific benchmarks
    BENCHMARK_META = Benchmark(
        benchmark_id="epoch_generic",
        name="Epoch AI Benchmark",
        category="general",
        description="Generic Epoch AI benchmark evaluation.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://epoch.ai/",
    )

    # Additional benchmark definitions for other Epoch CSVs
    ADDITIONAL_BENCHMARKS = {
        "gpqa_diamond": Benchmark(
            benchmark_id="gpqa_diamond",
            name="GPQA Diamond",
            category="reasoning",
            description="Graduate-level science questions requiring expert knowledge.",
            unit="percent",
            scale_min=0.0,
            scale_max=100.0,
            higher_is_better=True,
            official_url="https://arxiv.org/abs/2311.12022",
        ),
        "math_level_5": Benchmark(
            benchmark_id="math_level_5",
            name="MATH (Level 5)",
            category="math",
            description="Competition mathematics problems at the hardest difficulty level.",
            unit="percent",
            scale_min=0.0,
            scale_max=100.0,
            higher_is_better=True,
            official_url="https://arxiv.org/abs/2103.03874",
        ),
        "aider_polyglot": Benchmark(
            benchmark_id="aider_polyglot",
            name="Aider Polyglot",
            category="coding",
            description="Code editing benchmark across multiple programming languages.",
            unit="percent",
            scale_min=0.0,
            scale_max=100.0,
            higher_is_better=True,
            official_url="https://aider.chat/docs/leaderboards/",
        ),
    }

    def __init__(self, benchmark_id: str = "epoch_generic", csv_path: Path | None = None):
        """Initialize with specific benchmark configuration.

        Args:
            benchmark_id: ID of the benchmark to ingest
            csv_path: Optional path to CSV file
        """
        super().__init__()
        self.BENCHMARK_ID = benchmark_id
        self._csv_path = csv_path

        # Use specific benchmark metadata if available
        if benchmark_id in self.ADDITIONAL_BENCHMARKS:
            self.BENCHMARK_META = self.ADDITIONAL_BENCHMARKS[benchmark_id]

    def fetch_raw(self) -> Path:
        """Load data from specified CSV path."""
        if self._csv_path and self._csv_path.exists():
            return self._csv_path

        # Try common locations
        csv_names = [
            f"{self.BENCHMARK_ID}.csv",
            f"{self.BENCHMARK_ID}_external.csv",
        ]

        for csv_name in csv_names:
            workspace_path = Path("/sessions/elegant-modest-turing/mnt/Programming") / csv_name
            if workspace_path.exists():
                return workspace_path

        raise FileNotFoundError(
            f"CSV not found for {self.BENCHMARK_ID}. "
            f"Tried: {csv_names}"
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse Epoch-format CSV into Result objects."""
        df = pl.read_csv(raw_path)

        # Create source record
        source = Source(
            source_id=self.generate_source_id(f"https://epoch.ai/{self.BENCHMARK_ID}"),
            source_type=SourceType.THIRD_PARTY_LEADERBOARD,
            source_title=f"Epoch AI {self.BENCHMARK_META.name} Evaluations",
            source_url=self.BENCHMARK_META.official_url or "https://epoch.ai/",
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        # Detect score column name
        score_col = None
        for col in ["Best score (across scorers)", "score", "accuracy", "Score"]:
            if col in df.columns:
                score_col = col
                break

        if not score_col:
            self.log_error(f"Could not find score column in {raw_path}")
            return results

        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("Model version", row.get("model", ""))
                if not model_name:
                    continue

                provider = row.get("Organization", row.get("organization", "Unknown"))
                release_date = self.parse_date(
                    row.get("Release date", row.get("release_date"))
                )

                model_id = self.normalize_model_id(model_name, provider)
                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    release_date=release_date,
                    status=ModelStatus.VERIFIED,
                    training_compute_flop=self._parse_float(row.get("Training compute (FLOP)")),
                )
                self.register_model(model)

                # Parse score
                raw_score = self._parse_float(row.get(score_col))
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
                    trust_tier=TrustTier.B,
                    evaluation_notes=f"Epoch AI evaluation",
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
            "gpt-3.5": ["gpt-3.5"],
            "o1": ["o1-"],
            "o3": ["o3-"],
            "claude-3": ["claude-3"],
            "claude-3.5": ["claude-3-5", "claude-3.5"],
            "gemini": ["gemini"],
            "grok": ["grok"],
            "llama": ["llama"],
            "deepseek": ["deepseek"],
            "qwen": ["qwen"],
            "mistral": ["mistral", "mixtral"],
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
