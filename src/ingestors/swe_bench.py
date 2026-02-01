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

    Data source: Official swebench.com leaderboard (curated snapshot)
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

    def fetch_raw(self) -> Path:
        """Fetch SWE-Bench data from curated snapshot.

        Returns path to the local snapshot CSV with data from swebench.com.
        """
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "swe_bench_verified.csv"
        if not snapshot_path.exists():
            raise FileNotFoundError(f"SWE-Bench Verified snapshot not found: {snapshot_path}")
        return snapshot_path

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse SWE-Bench CSV into Result objects."""
        df = pl.read_csv(raw_path)

        # Create source record
        source = Source(
            source_id=self.generate_source_id("https://www.swebench.com/"),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="SWE-Bench Official Leaderboard",
            source_url="https://www.swebench.com/",
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CURATED_SNAPSHOT,
            raw_snapshot_path=str(raw_path),
            notes="Official SWE-Bench Verified leaderboard results",
        )
        self.register_source(source)

        results = []
        for row in df.iter_rows(named=True):
            try:
                # Parse model info
                model_name = row.get("model", "")
                if not model_name:
                    continue

                provider = row.get("provider", "Unknown")
                release_date = self.parse_date(row.get("date"))

                # Create/register model
                model_id = self.normalize_model_id(model_name, provider)
                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    release_date=release_date,
                    status=ModelStatus.VERIFIED,
                    metadata={
                        "notes": row.get("notes", ""),
                    },
                )
                self.register_model(model)

                # Parse score (already in percentage)
                score = self._parse_float(row.get("score"))

                # Create result
                result = Result(
                    result_id=self.generate_result_id(model_id, release_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    evaluation_date=release_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,  # Official leaderboard
                    evaluation_notes=row.get("notes", ""),
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
