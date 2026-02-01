"""Epoch Capabilities Index ingestor - composite index of frontier AI capabilities."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class EpochCapabilitiesIndexIngestor(BaseIngestor):
    """Ingestor for Epoch Capabilities Index benchmark."""

    BENCHMARK_ID = "epoch_capabilities_index"
    LEADERBOARD_URL = "https://epoch.ai/benchmarks/eci"

    BENCHMARK_META = Benchmark(
        benchmark_id="epoch_capabilities_index",
        name="Epoch Capabilities Index",
        category="general",
        description="Composite index of frontier AI capabilities. GPT-4 baseline = 100, higher values indicate stronger capability.",
        unit="index",
        scale_min=0.0,
        scale_max=200.0,
        higher_is_better=True,
        official_url="https://epoch.ai/benchmarks/eci",
    )

    def fetch_raw(self) -> Path:
        """Fetch Epoch Capabilities Index data from snapshot."""
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "epoch_capabilities_index.csv"

        if snapshot_path.exists():
            return snapshot_path

        raise FileNotFoundError(
            f"Epoch Capabilities Index snapshot not found at {snapshot_path}. "
            "Please download from epoch.ai."
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse Epoch Capabilities Index CSV."""
        df = pl.read_csv(raw_path)

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.THIRD_PARTY_LEADERBOARD,
            source_title="Epoch AI Notable Models",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("model") or row.get("Model") or row.get("System") or ""
                if not model_name:
                    continue

                provider = row.get("provider") or row.get("Organization") or self._infer_provider(model_name)
                score = self._parse_float(row.get("score") or row.get("Score") or row.get("capabilities_index"))
                eval_date = self.parse_date(row.get("date") or row.get("Publication date"))

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
                    trust_tier=TrustTier.B,  # Third-party source
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")

        return results

    def _parse_float(self, value) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
