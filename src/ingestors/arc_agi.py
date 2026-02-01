"""ARC-AGI benchmark ingestors (versions 1 and 2).

ARC-AGI 1: Uses Epoch AI data (from arc_agi_external.csv)
ARC-AGI 2: Scraped from arcprize.org leaderboard (different benchmark, harder tasks)
"""

import json
import logging
import re
from datetime import datetime, date
from pathlib import Path

import httpx
import polars as pl

from .base import BaseIngestor
from .epoch_fetcher import get_epoch_csv
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)

logger = logging.getLogger(__name__)


class ARCAGI1Ingestor(BaseIngestor):
    """Ingestor for ARC-AGI 1 (original).

    Data source: Epoch AI (arc_agi_external.csv)
    This is the original ARC-AGI benchmark measuring basic fluid intelligence.
    """

    BENCHMARK_ID = "arc_agi_1"
    LEADERBOARD_URL = "https://arcprize.org/leaderboard"

    BENCHMARK_META = Benchmark(
        benchmark_id="arc_agi_1",
        name="ARC-AGI 1",
        category="reasoning",
        description="Original Abstraction and Reasoning Corpus evaluating fluid intelligence and novel problem solving. Scores are accuracy on the semi-private evaluation set.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://arcprize.org/leaderboard",
        paper_url="https://arxiv.org/abs/1911.01547",
        notes="Scores from ARC Prize leaderboard via Epoch AI. Expressed as percentage (0-100).",
    )

    def fetch_raw(self) -> Path:
        """Fetch ARC-AGI 1 data from Epoch AI."""
        return get_epoch_csv("arc_agi_external.csv")

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse ARC-AGI CSV into Result objects."""
        df = pl.read_csv(raw_path)

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="ARC Prize 1 Leaderboard (via Epoch AI)",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("Model version") or row.get("model") or ""
                if not model_name:
                    continue

                provider = row.get("Organization") or self._infer_provider(model_name)
                raw_score = self._parse_float(row.get("Score"))
                eval_date = self.parse_date(row.get("Release date"))

                if raw_score is None:
                    continue

                # Convert 0-1 score to percentage
                score = raw_score * 100 if raw_score <= 1 else raw_score

                model_id = self.normalize_model_id(model_name, provider)

                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
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
                    evaluation_notes=f"ARC-AGI 1 official result. Source: {row.get('Source', 'ARC Prize')}",
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


class ARCAGI2Ingestor(BaseIngestor):
    """Ingestor for ARC-AGI 2.

    Data source: Scraped from arcprize.org leaderboard
    ARC-AGI 2 is a harder benchmark with improved evaluation methodology.

    Note: Epoch AI does NOT have ARC-2 data, so we scrape the official leaderboard.
    """

    BENCHMARK_ID = "arc_agi_2"
    LEADERBOARD_URL = "https://arcprize.org/leaderboard"
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "scraped"

    BENCHMARK_META = Benchmark(
        benchmark_id="arc_agi_2",
        name="ARC-AGI 2",
        category="reasoning",
        description="Updated ARC-AGI with harder tasks and improved evaluation methodology. Requires both high adaptability and high efficiency.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://arcprize.org/leaderboard",
        notes="Scraped from ARC Prize leaderboard. ARC-2 is significantly harder than ARC-1.",
    )

    def fetch_raw(self) -> Path:
        """Fetch ARC-AGI 2 data from snapshot.

        ARC-AGI 2 data is obtained from arcprize.org leaderboard.
        Since the site uses client-side rendering, we maintain a curated snapshot.
        """
        # Use curated snapshot - ARC Prize site uses JS rendering
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "arc_agi_2.csv"
        if snapshot_path.exists():
            logger.info(f"Using ARC-AGI 2 snapshot from {snapshot_path}")
            return snapshot_path

        raise FileNotFoundError(
            "ARC-AGI 2 snapshot not found. Please create data/snapshots/arc_agi_2.csv "
            "with data from https://arcprize.org/leaderboard"
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse ARC-AGI 2 data."""
        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL + "/v2"),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="ARC Prize 2 Leaderboard",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.HTML_SCRAPE,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        # Handle JSON format
        if raw_path.suffix == ".json":
            try:
                data = json.loads(raw_path.read_text())
                entries = data.get("entries", data.get("leaderboard", []))
                if isinstance(data, list):
                    entries = data

                for entry in entries:
                    result = self._parse_entry(entry, source.source_id)
                    if result:
                        results.append(result)
            except (json.JSONDecodeError, KeyError) as e:
                self.log_warning(f"Failed to parse JSON: {e}")

        # Handle CSV format (from snapshot)
        elif raw_path.suffix == ".csv":
            try:
                df = pl.read_csv(raw_path)
                for row in df.iter_rows(named=True):
                    result = self._parse_csv_row(row, source.source_id)
                    if result:
                        results.append(result)
            except Exception as e:
                self.log_warning(f"Failed to parse CSV: {e}")

        return results

    def _parse_entry(self, entry: dict, source_id: str) -> Result | None:
        """Parse a JSON leaderboard entry."""
        try:
            model_name = entry.get("model") or entry.get("name") or entry.get("Model version")
            if not model_name:
                return None

            provider = entry.get("organization") or entry.get("provider") or self._infer_provider(model_name)
            raw_score = entry.get("score") or entry.get("accuracy")

            if raw_score is None:
                return None

            score = float(raw_score)
            # Convert 0-1 to percentage if needed
            if score <= 1:
                score = score * 100

            eval_date = self.parse_date(entry.get("date") or entry.get("release_date"))
            model_id = self.normalize_model_id(model_name, provider)

            model = Model(
                model_id=model_id,
                name=model_name,
                provider=provider,
                family=self._infer_family(model_name),
                release_date=eval_date,
                status=ModelStatus.VERIFIED,
            )
            self.register_model(model)

            return Result(
                result_id=self.generate_result_id(model_id, eval_date),
                model_id=model_id,
                benchmark_id=self.BENCHMARK_ID,
                score=score,
                evaluation_date=eval_date,
                source_id=source_id,
                trust_tier=TrustTier.A,
                evaluation_notes="ARC-AGI 2 official result",
            )
        except Exception as e:
            self.log_warning(f"Failed to parse entry: {e}")
            return None

    def _parse_csv_row(self, row: dict, source_id: str) -> Result | None:
        """Parse a CSV row."""
        try:
            model_name = row.get("model") or row.get("Model") or row.get("Model version")
            if not model_name:
                return None

            provider = row.get("provider") or row.get("Organization") or self._infer_provider(model_name)
            raw_score = row.get("score") or row.get("Score")

            if raw_score is None:
                return None

            score = float(raw_score)
            if score <= 1:
                score = score * 100

            eval_date = self.parse_date(row.get("date") or row.get("Release date"))
            model_id = self.normalize_model_id(model_name, provider)

            model = Model(
                model_id=model_id,
                name=model_name,
                provider=provider,
                family=self._infer_family(model_name),
                release_date=eval_date,
                status=ModelStatus.VERIFIED,
            )
            self.register_model(model)

            return Result(
                result_id=self.generate_result_id(model_id, eval_date),
                model_id=model_id,
                benchmark_id=self.BENCHMARK_ID,
                score=score,
                evaluation_date=eval_date,
                source_id=source_id,
                trust_tier=TrustTier.A,
                evaluation_notes="ARC-AGI 2 official result",
            )
        except Exception as e:
            self.log_warning(f"Failed to parse row: {e}")
            return None

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
