"""Remote Labor Index ingestor - METR's practical work capability benchmark."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class RemoteLaborIndexIngestor(BaseIngestor):
    """Ingestor for Remote Labor Index benchmark."""

    BENCHMARK_ID = "remote_labor_index"
    LEADERBOARD_URL = "https://scale.com/leaderboard/rli"

    BENCHMARK_META = Benchmark(
        benchmark_id="remote_labor_index",
        name="Remote Labor Index",
        category="agentic",
        description="Evaluates AI systems on remote labor tasks measuring practical work capability.",
        unit="hours",
        scale_min=0.0,
        scale_max=1000.0,
        higher_is_better=True,
        official_url="https://scale.com/leaderboard/rli",
    )

    def fetch_raw(self) -> Path:
        """Fetch Remote Labor Index data from snapshot."""
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "remote_labor_index.csv"

        if snapshot_path.exists():
            return snapshot_path

        raise FileNotFoundError(
            f"Remote Labor Index snapshot not found at {snapshot_path}. "
            "Please download from metr.org."
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse Remote Labor Index CSV."""
        df = pl.read_csv(raw_path)

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="Remote Labor Index Leaderboard",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("model") or row.get("Model") or ""
                if not model_name:
                    continue

                provider = row.get("provider") or self._infer_provider(model_name)
                score = self._parse_float(row.get("score") or row.get("Score") or row.get("hours"))
                eval_date = self.parse_date(row.get("date"))

                model_id = self.normalize_model_id(model_name, provider)

                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    release_date=eval_date,
                    status=ModelStatus.VERIFIED,
                )
                self.register_model(model)

                result = Result(
                    result_id=self.generate_result_id(model_id, eval_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    evaluation_date=eval_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")

        return results

    def _parse_float(self, value) -> float | None:
        """Parse float value - no conversion needed as unit is hours."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
