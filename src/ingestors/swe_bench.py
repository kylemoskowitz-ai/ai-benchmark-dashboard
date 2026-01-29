"""SWE-Bench Verified benchmark ingestor."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class SWEBenchIngestor(BaseIngestor):
    """Ingestor for SWE-Bench Verified benchmark.

    SWE-Bench evaluates AI models on real-world software engineering tasks
    from GitHub issues. The "Verified" subset contains human-verified test cases.

    Data source: Epoch AI evaluations (epoch.ai)
    """

    BENCHMARK_ID = "swe_bench_verified"

    BENCHMARK_META = Benchmark(
        benchmark_id="swe_bench_verified",
        name="SWE-Bench Verified",
        category="coding",
        description=(
            "SWE-Bench evaluates models on real GitHub issues. "
            "The Verified subset contains 500 human-verified test cases."
        ),
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://www.swebench.com/",
        paper_url="https://arxiv.org/abs/2310.06770",
        notes="Score represents percentage of issues resolved correctly.",
    )

    # Path to local snapshot (relative to project root or workspace)
    SNAPSHOT_PATHS = [
        Path("swe_bench_verified.csv"),  # In workspace root
        Path("data/snapshots/swe_bench_verified.csv"),  # In project snapshots
    ]

    def fetch_raw(self) -> Path:
        """Load SWE-Bench data from local CSV snapshot.

        The CSV is from Epoch AI's benchmark evaluations.
        """
        # Try to find the snapshot
        for rel_path in self.SNAPSHOT_PATHS:
            # Check workspace root first
            workspace_path = Path("/sessions/elegant-modest-turing/mnt/Programming") / rel_path
            if workspace_path.exists():
                return workspace_path

            # Check project directory
            project_path = Path("/sessions/elegant-modest-turing/mnt/Programming/ai-benchmark-dashboard") / rel_path
            if project_path.exists():
                return project_path

        raise FileNotFoundError(
            f"SWE-Bench snapshot not found. Tried: {self.SNAPSHOT_PATHS}"
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse SWE-Bench CSV into Result objects."""
        df = pl.read_csv(raw_path)

        # Create source record
        source = Source(
            source_id=self.generate_source_id("https://epoch.ai/data/swe_bench_verified"),
            source_type=SourceType.THIRD_PARTY_LEADERBOARD,
            source_title="Epoch AI SWE-Bench Verified Evaluations",
            source_url="https://epoch.ai/data/swe_bench_verified",
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
            notes="Epoch AI's standardized evaluations of models on SWE-Bench Verified",
        )
        self.register_source(source)

        results = []
        for row in df.iter_rows(named=True):
            try:
                # Parse model info
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
                        "log_viewer": row.get("Log viewer", ""),
                    },
                )
                self.register_model(model)

                # Parse score (convert from 0-1 to percentage if needed)
                raw_score = self._parse_float(row.get("Best score (across scorers)"))
                if raw_score is not None:
                    # Epoch data is 0-1, convert to percentage
                    score = raw_score * 100 if raw_score <= 1 else raw_score
                else:
                    score = None

                # Parse stderr
                stderr = self._parse_float(row.get("stderr"))
                if stderr is not None and stderr <= 1:
                    stderr = stderr * 100  # Convert to percentage

                # Parse evaluation date
                eval_date = self.parse_date(row.get("Started at"))

                # Create result
                result = Result(
                    result_id=self.generate_result_id(model_id, eval_date or release_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    score_stderr=stderr,
                    evaluation_date=eval_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.B,  # Epoch AI = semi-official
                    evaluation_notes=f"Epoch AI evaluation. Log ID: {row.get('id', 'N/A')}",
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
            "gpt-3.5": ["gpt-3.5", "gpt3.5"],
            "o1": ["o1-"],
            "o3": ["o3-"],
            "o4": ["o4-"],
            "claude-3.5": ["claude-3-5", "claude-3.5", "sonnet-3.5"],
            "claude-3.7": ["claude-3-7", "claude-3.7"],
            "claude-4": ["claude-4", "sonnet-4", "opus-4"],
            "gemini-1.5": ["gemini-1.5", "gemini-1-5"],
            "gemini-2": ["gemini-2"],
            "grok-3": ["grok-3"],
            "llama-3": ["llama-3", "llama3"],
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
