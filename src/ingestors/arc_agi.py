"""ARC-AGI benchmark ingestors (versions 1 and 2)."""

from datetime import datetime, date
from pathlib import Path
import httpx
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class ARCAGIBaseIngestor(BaseIngestor):
    """Base ingestor for ARC-AGI benchmarks."""

    # Override in subclasses
    LEADERBOARD_URL = ""
    VERSION = ""

    def fetch_raw(self) -> Path:
        """Fetch ARC-AGI leaderboard data."""
        # Try local snapshot first
        snapshot_name = f"arc_agi_{self.VERSION}.csv"
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / snapshot_name

        if snapshot_path.exists():
            return snapshot_path

        # Otherwise fetch from web
        # Note: ARC Prize doesn't have a public API, so we rely on snapshots
        raise FileNotFoundError(
            f"ARC-AGI {self.VERSION} snapshot not found at {snapshot_path}. "
            "Please download manually from arcprize.org."
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse ARC-AGI CSV into Result objects."""
        df = pl.read_csv(raw_path)

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title=f"ARC Prize {self.VERSION} Leaderboard",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        # Expected columns: model, provider, score, date, reasoning_effort (optional)
        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("model") or row.get("Model") or ""
                if not model_name:
                    continue

                provider = row.get("provider") or row.get("Provider") or self._infer_provider(model_name)
                score = self._parse_float(row.get("score") or row.get("Score"))
                eval_date = self.parse_date(row.get("date") or row.get("Date"))
                reasoning_effort = row.get("reasoning_effort") or row.get("Reasoning Effort")

                # Include reasoning effort in model name if present
                display_name = model_name
                if reasoning_effort:
                    display_name = f"{model_name} ({reasoning_effort})"

                model_id = self.normalize_model_id(display_name, provider)

                model = Model(
                    model_id=model_id,
                    name=display_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    release_date=eval_date,
                    status=ModelStatus.VERIFIED,
                    metadata={"reasoning_effort": reasoning_effort} if reasoning_effort else {},
                )
                self.register_model(model)

                result = Result(
                    result_id=self.generate_result_id(model_id, eval_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    evaluation_date=eval_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,  # Official leaderboard
                    evaluation_notes=f"ARC Prize {self.VERSION} official result",
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")

        return results

    def _infer_family(self, model_name: str) -> str | None:
        name_lower = model_name.lower()
        families = {
            "o3": ["o3"], "o4": ["o4"], "o1": ["o1"],
            "gpt-4": ["gpt-4"], "gpt-5": ["gpt-5"],
            "claude-4": ["claude-4", "opus-4", "sonnet-4"],
            "claude-3.5": ["claude-3-5", "claude-3.5"],
            "gemini-2": ["gemini-2"], "gemini-3": ["gemini-3"],
        }
        for family, patterns in families.items():
            for p in patterns:
                if p in name_lower:
                    return family
        return None

    def _parse_float(self, value) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class ARCAGI1Ingestor(ARCAGIBaseIngestor):
    """Ingestor for ARC-AGI 1 (original)."""

    BENCHMARK_ID = "arc_agi_1"
    VERSION = "1"
    LEADERBOARD_URL = "https://arcprize.org/leaderboard"

    BENCHMARK_META = Benchmark(
        benchmark_id="arc_agi_1",
        name="ARC-AGI 1",
        category="reasoning",
        description="Original Abstraction and Reasoning Corpus evaluating fluid intelligence and novel problem solving.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://arcprize.org/",
        paper_url="https://arxiv.org/abs/1911.01547",
    )


class ARCAGI2Ingestor(ARCAGIBaseIngestor):
    """Ingestor for ARC-AGI 2."""

    BENCHMARK_ID = "arc_agi_2"
    VERSION = "2"
    LEADERBOARD_URL = "https://arcprize.org/arc-agi-2"

    BENCHMARK_META = Benchmark(
        benchmark_id="arc_agi_2",
        name="ARC-AGI 2",
        category="reasoning",
        description="Updated ARC-AGI with harder tasks and improved evaluation methodology.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://arcprize.org/arc-agi-2",
    )
