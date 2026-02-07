"""External impact-signal ingestors for economic diffusion tracking."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable
import math

import httpx
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Benchmark,
    Model,
    ModelStatus,
    ParseMethod,
    Result,
    Source,
    SourceType,
    TrustTier,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "impact"
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshots"

US_MODEL_NAME = "US Labor Market"
US_PROVIDER = "Public Economic Data"


class _ExternalImpactBase(BaseIngestor):
    """Shared fetch/parse helpers for external impact signals."""

    DATA_URL: str = ""
    SNAPSHOT_FILENAME: str = ""
    EMPTY_HEADER: str = "date,value\n"
    SOURCE_TITLE: str = ""
    SOURCE_TYPE: SourceType = SourceType.THIRD_PARTY_LEADERBOARD

    def fetch_raw(self) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CACHE_DIR / self.SNAPSHOT_FILENAME
        snapshot_path = SNAPSHOT_DIR / self.SNAPSHOT_FILENAME

        try:
            response = httpx.get(self.DATA_URL, timeout=45.0)
            response.raise_for_status()
            cache_path.write_bytes(response.content)
            return cache_path
        except Exception as exc:
            self.log_warning(f"External fetch failed for {self.BENCHMARK_ID}: {exc}")

        if cache_path.exists():
            self.log_warning(f"Using stale cached data for {self.BENCHMARK_ID}")
            return cache_path

        if snapshot_path.exists():
            self.log_warning(f"Using local snapshot for {self.BENCHMARK_ID}")
            return snapshot_path

        # Keep pipeline resilient even when external data is temporarily unavailable.
        cache_path.write_text(self.EMPTY_HEADER, encoding="utf-8")
        self.log_warning(f"No cache/snapshot for {self.BENCHMARK_ID}; writing empty dataset")
        return cache_path

    def _register_source(self, raw_path: Path) -> Source:
        source = Source(
            source_id=self.generate_source_id(self.DATA_URL),
            source_type=self.SOURCE_TYPE,
            source_title=self.SOURCE_TITLE,
            source_url=self.DATA_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)
        return source

    def _register_us_model(self) -> str:
        model_id = self.normalize_model_id(US_MODEL_NAME, US_PROVIDER)
        model = Model(
            model_id=model_id,
            name=US_MODEL_NAME,
            provider=US_PROVIDER,
            family="Economic signal",
            status=ModelStatus.VERIFIED,
        )
        self.register_model(model)
        return model_id

    def validate(self, results: list[Result]) -> list[Result]:
        """Validate impact signals with flexible upper bounds.

        These series can exceed display-scale assumptions over time, so we only
        enforce non-negative finite values and required provenance.
        """
        validated: list[Result] = []
        for r in results:
            try:
                if r.score is not None and (not math.isfinite(r.score) or r.score < 0):
                    self.log_warning(f"Invalid score {r.score} for {r.model_id}")
                    continue
                if not r.source_id:
                    self.log_error(f"Missing source_id for {r.model_id}")
                    continue
                validated.append(r)
            except Exception as exc:
                self.log_error(f"Validation error for {r.model_id}: {exc}")
        return validated

    @staticmethod
    def _clean_date(date_text: str | None) -> str | None:
        if not date_text:
            return None
        return str(date_text).strip()

    def _normalize_share_value(self, value: float) -> float:
        """Normalize share values without over-scaling.

        Prefer raw values when they are already within a plausible UI scale.
        Only apply x100 if raw looks implausible but the scaled value does.
        """
        bench_max = self.BENCHMARK_META.scale_max if self.BENCHMARK_META else None
        raw = float(value)
        scaled = raw * 100.0

        if bench_max is None:
            return raw

        tolerance_max = bench_max * 1.25
        if 0 <= raw <= tolerance_max:
            return raw
        if 0 <= scaled <= tolerance_max:
            return scaled
        return raw

    @staticmethod
    def _find_first_column(columns: Iterable[str], names: set[str]) -> str | None:
        lowered = {
            _ExternalImpactBase._normalize_column_name(c): c for c in columns
        }
        for candidate in names:
            key = _ExternalImpactBase._normalize_column_name(candidate)
            if key in lowered:
                return lowered[key]
        return None

    @staticmethod
    def _normalize_column_name(name: str) -> str:
        return "".join(ch for ch in str(name).lower() if ch.isalnum())


class _IndeedPostingShareIngestor(_ExternalImpactBase):
    """Base ingestor for Indeed Hiring Lab posting-share series."""

    SOURCE_TITLE = "Indeed Hiring Lab AI Tracker"
    SOURCE_TYPE = SourceType.THIRD_PARTY_LEADERBOARD
    EMPTY_HEADER = "date,JobCountry,share\n"
    COUNTRY_FILTER = "US"

    SHARE_COLUMN_HINTS: tuple[str, ...] = ()

    def parse(self, raw_path: Path) -> list[Result]:
        source = self._register_source(raw_path)
        model_id = self._register_us_model()
        results: list[Result] = []

        try:
            df = pl.read_csv(raw_path, ignore_errors=True)
        except Exception as exc:
            self.log_warning(f"Failed to read {self.BENCHMARK_ID} csv: {exc}")
            return []

        if df.is_empty():
            return []

        date_col = self._find_first_column(df.columns, {"date"})
        country_col = self._find_first_column(
            df.columns,
            {"jobcountry", "country", "location", "region"},
        )
        share_col = self._detect_share_column(df.columns)

        if not date_col or not share_col:
            self.log_warning(
                f"{self.BENCHMARK_ID}: missing required columns (date/share), found={df.columns}"
            )
            return []

        table = df
        if country_col:
            table = table.filter(
                pl.col(country_col).cast(pl.Utf8, strict=False).str.to_uppercase()
                == self.COUNTRY_FILTER
            )
        if table.is_empty():
            return []

        table = (
            table.select(
                pl.col(date_col).cast(pl.Utf8, strict=False).alias("date"),
                pl.col(share_col).cast(pl.Float64, strict=False).alias("score"),
            )
            .filter(pl.col("date").is_not_null() & pl.col("score").is_not_null())
            .group_by("date")
            .agg(pl.col("score").max().alias("score"))
            .sort("date")
        )

        for row in table.iter_rows(named=True):
            eval_date = self.parse_date(self._clean_date(row.get("date")))
            score = row.get("score")
            if eval_date is None or score is None:
                continue

            value = self._normalize_share_value(float(score))
            results.append(
                Result(
                    result_id=self.generate_result_id(model_id, eval_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=value,
                    evaluation_date=eval_date,
                    subset="US",
                    source_id=source.source_id,
                    trust_tier=TrustTier.B,
                    evaluation_notes="US series from Indeed Hiring Lab AI tracker.",
                )
            )

        return results

    def _detect_share_column(self, columns: list[str]) -> str | None:
        lowered = {
            self._normalize_column_name(c): c for c in columns
        }

        for hint in self.SHARE_COLUMN_HINTS:
            key = self._normalize_column_name(hint)
            if key in lowered:
                return lowered[key]

        for column in columns:
            c = column.lower()
            if "share" in c and c not in {"market_share", "share_class"}:
                return column
        return None


class AIJobPostingsShareIngestor(_IndeedPostingShareIngestor):
    """Share of job postings mentioning AI skills (US)."""

    BENCHMARK_ID = "ai_job_postings_share"
    DATA_URL = "https://raw.githubusercontent.com/hiring-lab/ai-tracker/main/AI_posting.csv"
    SNAPSHOT_FILENAME = "ai_job_postings_share.csv"
    SHARE_COLUMN_HINTS = ("ai_share", "ai_posting_share")

    BENCHMARK_META = Benchmark(
        benchmark_id="ai_job_postings_share",
        name="AI Job Posting Share (US)",
        category="impact",
        description="Share of US job postings requiring AI-related skills (Indeed Hiring Lab).",
        unit="percent",
        scale_min=0.0,
        scale_max=10.0,
        higher_is_better=True,
        official_url="https://github.com/hiring-lab/ai-tracker",
        notes="US labor-demand diffusion proxy. Higher values imply broader employer demand for AI skills.",
    )


class GenAIJobPostingsShareIngestor(_IndeedPostingShareIngestor):
    """Share of job postings mentioning GenAI skills (US)."""

    BENCHMARK_ID = "genai_job_postings_share"
    DATA_URL = "https://raw.githubusercontent.com/hiring-lab/ai-tracker/main/GenAI_posting.csv"
    SNAPSHOT_FILENAME = "genai_job_postings_share.csv"
    SHARE_COLUMN_HINTS = ("genai_share", "gen_ai_share", "genai_posting_share")

    BENCHMARK_META = Benchmark(
        benchmark_id="genai_job_postings_share",
        name="GenAI Job Posting Share (US)",
        category="impact",
        description="Share of US job postings explicitly requiring GenAI skills (Indeed Hiring Lab).",
        unit="percent",
        scale_min=0.0,
        scale_max=6.0,
        higher_is_better=True,
        official_url="https://github.com/hiring-lab/ai-tracker",
        notes="Narrower labor-demand diffusion proxy focused on generative AI skills.",
    )


class LaborProductivityIndexIngestor(_ExternalImpactBase):
    """US nonfarm labor productivity index (BLS via FRED)."""

    BENCHMARK_ID = "labor_productivity_index"
    DATA_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=OPHNFB"
    SNAPSHOT_FILENAME = "labor_productivity_index.csv"
    SOURCE_TITLE = "FRED OPHNFB (BLS labor productivity)"
    SOURCE_TYPE = SourceType.OFFICIAL_LEADERBOARD
    EMPTY_HEADER = "DATE,OPHNFB\n"

    BENCHMARK_META = Benchmark(
        benchmark_id="labor_productivity_index",
        name="US Labor Productivity (Index)",
        category="economy",
        description="BLS nonfarm business labor productivity index (FRED series OPHNFB).",
        unit="index",
        scale_min=80.0,
        scale_max=140.0,
        higher_is_better=True,
        official_url="https://fred.stlouisfed.org/series/OPHNFB",
        notes="Quarterly macroeconomic adoption proxy. Higher values indicate greater output per hour.",
    )

    def parse(self, raw_path: Path) -> list[Result]:
        source = self._register_source(raw_path)
        model_id = self._register_us_model()
        results: list[Result] = []

        try:
            df = pl.read_csv(raw_path, ignore_errors=True)
        except Exception as exc:
            self.log_warning(f"Failed to read labor productivity csv: {exc}")
            return []

        if df.is_empty():
            return []

        date_col = self._find_first_column(df.columns, {"date"})
        value_col = next((c for c in df.columns if c.lower() != "date"), None)
        if not date_col or not value_col:
            self.log_warning(f"{self.BENCHMARK_ID}: missing date/value columns, found={df.columns}")
            return []

        table = (
            df.select(
                pl.col(date_col).cast(pl.Utf8, strict=False).alias("date"),
                pl.col(value_col).cast(pl.Float64, strict=False).alias("score"),
            )
            .filter(pl.col("date").is_not_null() & pl.col("score").is_not_null())
            .group_by("date")
            .agg(pl.col("score").max().alias("score"))
            .sort("date")
        )

        for row in table.iter_rows(named=True):
            eval_date = self.parse_date(self._clean_date(row.get("date")))
            score = row.get("score")
            if eval_date is None or score is None:
                continue

            results.append(
                Result(
                    result_id=self.generate_result_id(model_id, eval_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=float(score),
                    evaluation_date=eval_date,
                    subset="US",
                    source_id=source.source_id,
                    trust_tier=TrustTier.B,
                    evaluation_notes="FRED OPHNFB series (BLS nonfarm business labor productivity).",
                )
            )

        return results
