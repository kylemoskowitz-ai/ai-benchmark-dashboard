"""ZeroBench ingestor - zero-shot visual understanding benchmark."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from .web_scraper import scrape_zerobench, write_scraped_to_csv
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class ZeroBenchIngestor(BaseIngestor):
    """Ingestor for ZeroBench.

    Data source: Scraped from zerobench.github.io (cached for 6 hours)
    """

    BENCHMARK_ID = "zerobench"
    LEADERBOARD_URL = "https://zerobench.github.io/"

    BENCHMARK_META = Benchmark(
        benchmark_id="zerobench",
        name="ZeroBench",
        category="multimodal",
        description="An 'impossible' visual benchmark for contemporary large multimodal models. Scores represent pass@5 accuracy - the percentage of tasks solved correctly in 5 attempts.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://zerobench.github.io/",
        notes="Scores are pass@5 accuracy. This benchmark is designed to be extremely challenging.",
    )

    def fetch_raw(self) -> Path:
        """Fetch ZeroBench data from snapshot.

        The ZeroBench website uses client-side rendering, so we maintain
        a curated snapshot from zerobench.github.io.
        """
        # Use curated snapshot - site uses JS rendering
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "zerobench.csv"
        if snapshot_path.exists():
            return snapshot_path

        raise FileNotFoundError(
            "ZeroBench snapshot not found. Please create data/snapshots/zerobench.csv "
            "with data from https://zerobench.github.io/"
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse ZeroBench CSV."""
        df = pl.read_csv(raw_path)

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="ZeroBench Leaderboard",
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
                score = self._parse_float(row.get("score") or row.get("Score"))
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
        """Parse score - ZeroBench scores are already in percentage (0-100)."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
