"""ARC-AGI benchmark ingestors (versions 1 and 2).

ARC-AGI 1: ARC Prize leaderboard (official) with snapshot fallbacks.
ARC-AGI 2: ARC Prize leaderboard (official) with snapshot fallbacks.
"""

import json
import logging
import re
from datetime import datetime, date
from pathlib import Path

import httpx
import polars as pl

from .base import BaseIngestor
from .arcprize_fetcher import get_arcprize_snapshot, load_arcprize_snapshot
from .epoch_fetcher import get_epoch_csv
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)

logger = logging.getLogger(__name__)

MODEL_NAME_BLOCKLIST = (
    "human",
    "panel",
    "baseline",
    "mturker",
    "stem_grad",
    "stem grad",
    "student",
    "teacher",
    "oracle",
    "average",
    "grader",
)

MODEL_DATE_PATTERN = re.compile(r"(20\d{2})[-_/](\d{2})[-_/](\d{2})")
MODEL_DATE_COMPACT_PATTERN = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
MODEL_ALLOWLIST_PATTERN = re.compile(
    r"^(?:openai|anthropic|google|meta|xai|mistral|deepseek|alibaba|moonshot)?[-_ ]*"
    r"(gpt|o[1-9]\d*|claude|gemini|grok|deepseek|qwen|llama|mistral|mixtral|kimi|magistral|codex|trm)\b",
    re.IGNORECASE,
)


def _is_valid_model_name(model_name: str) -> bool:
    if not model_name:
        return False
    name = model_name.strip().lower()
    if any(bad in name for bad in MODEL_NAME_BLOCKLIST):
        return False
    if not MODEL_ALLOWLIST_PATTERN.match(name):
        return False
    return True


def _extract_date_from_name(model_name: str) -> date | None:
    match = MODEL_DATE_PATTERN.search(model_name)
    if not match:
        match = MODEL_DATE_COMPACT_PATTERN.search(model_name)
    if not match:
        return None
    try:
        year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return date(year, month, day)
    except ValueError:
        return None


def _map_parse_method(value: str | None) -> ParseMethod:
    if value == "api":
        return ParseMethod.API
    if value == "html_scrape":
        return ParseMethod.HTML_SCRAPE
    return ParseMethod.CURATED_SNAPSHOT


def _score_to_percent(score: float) -> float:
    return score * 100 if score <= 1 else score


def _with_effort_suffix(model_name: str, effort: str | None) -> str:
    if not effort:
        return model_name
    effort_text = str(effort).strip()
    if not effort_text:
        return model_name
    if effort_text.lower() in model_name.lower():
        return model_name
    return f"{model_name} ({effort_text})"


class ARCAGI1Ingestor(BaseIngestor):
    """Ingestor for ARC-AGI 1 (original).

    Data source: ARC Prize leaderboard (official), with snapshot fallback.
    This is the original ARC-AGI benchmark measuring basic fluid intelligence.
    """

    BENCHMARK_ID = "arc_agi_1"
    LEADERBOARD_URL = "https://arcprize.org/leaderboard"
    CLEAR_EXISTING_RESULTS = True

    BENCHMARK_META = Benchmark(
        benchmark_id="arc_agi_1",
        name="ARC-AGI 1",
        category="reasoning",
        description="Original Abstraction and Reasoning Corpus evaluating fluid intelligence and novel problem solving. Scores are accuracy on the official ARC Prize ARC-AGI 1 evaluation split.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://arcprize.org/leaderboard",
        paper_url="https://arxiv.org/abs/1911.01547",
        notes="Scores from ARC Prize leaderboard (official), preferring ARC-AGI 1 semi-private split when available.",
    )

    def fetch_raw(self) -> Path:
        """Fetch ARC-AGI 1 data from ARC Prize leaderboard."""
        try:
            return get_arcprize_snapshot()
        except Exception as e:
            self.log_warning(f"ARC Prize fetch failed: {e}")

        try:
            return get_epoch_csv("arc_agi_external.csv")
        except Exception as e:
            self.log_warning(f"Epoch ARC-AGI data unavailable: {e}")

        return self.load_local_snapshot("arc_agi_1.csv")

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse ARC-AGI data into Result objects."""
        results = []

        if raw_path.suffix == ".json":
            data = load_arcprize_snapshot(raw_path)
            entries = data.get("benchmarks", {}).get(self.BENCHMARK_ID, [])
            source = Source(
                source_id=self.generate_source_id(data.get("source_url", self.LEADERBOARD_URL)),
                source_type=SourceType.OFFICIAL_LEADERBOARD,
                source_title="ARC Prize Leaderboard",
                source_url=data.get("source_url", self.LEADERBOARD_URL),
                retrieved_at=datetime.utcnow(),
                parse_method=_map_parse_method(data.get("parse_method")),
                raw_snapshot_path=str(raw_path),
            )
            self.register_source(source)

            for entry in entries:
                result = self._parse_arcprize_entry(entry, source.source_id)
                if result:
                    results.append(result)
            return results

        df = pl.read_csv(raw_path)
        is_epoch = "Model version" in df.columns or "Organization" in df.columns

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="ARC Prize Leaderboard (Epoch AI)" if is_epoch else "ARC Prize Leaderboard (Snapshot)",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD if is_epoch else ParseMethod.CURATED_SNAPSHOT,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        trust_tier = TrustTier.B if is_epoch else TrustTier.A

        for row in df.iter_rows(named=True):
            try:
                model_name = (
                    row.get("model")
                    or row.get("Model")
                    or row.get("Model version")
                    or row.get("model_name")
                    or ""
                )
                if not model_name or not _is_valid_model_name(model_name):
                    continue

                provider = row.get("provider") or row.get("Organization") or self._infer_provider(model_name)
                raw_score = self._parse_float(row.get("score") or row.get("Score"))
                eval_date = self.parse_date(row.get("date") or row.get("Release date")) or _extract_date_from_name(model_name)
                reasoning_effort = row.get("reasoning_effort")
                model_name = _with_effort_suffix(model_name, reasoning_effort)

                if raw_score is None:
                    continue

                score = _score_to_percent(raw_score)
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

                notes = row.get("Notes") or row.get("notes")
                note_parts = ["ARC-AGI 1 official result"]
                if reasoning_effort:
                    note_parts.append(f"effort={reasoning_effort}")
                if notes:
                    note_parts.append(str(notes))

                result = Result(
                    result_id=self.generate_result_id(model_id, eval_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    evaluation_date=eval_date,
                    subset=(row.get("dataset_id") or row.get("datasetId") or "").lower() or None,
                    source_id=source.source_id,
                    trust_tier=trust_tier,
                    evaluation_notes=". ".join(note_parts),
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")

        return results

    def _parse_arcprize_entry(self, entry: dict, source_id: str) -> Result | None:
        try:
            model_name = entry.get("model") or entry.get("name") or entry.get("Model version")
            if not model_name or not _is_valid_model_name(model_name):
                return None

            provider = entry.get("provider") or entry.get("organization") or self._infer_provider(model_name)
            raw_score = entry.get("score")
            if raw_score is None:
                return None

            score = _score_to_percent(float(raw_score))
            reasoning_effort = entry.get("reasoning_effort")
            model_name = _with_effort_suffix(model_name, reasoning_effort)
            eval_date = self.parse_date(entry.get("date")) or _extract_date_from_name(model_name)
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

            note_parts = ["ARC-AGI 1 official result"]
            if reasoning_effort:
                note_parts.append(f"effort={reasoning_effort}")
            if entry.get("notes"):
                note_parts.append(str(entry["notes"]))

            return Result(
                result_id=self.generate_result_id(model_id, eval_date),
                model_id=model_id,
                benchmark_id=self.BENCHMARK_ID,
                score=score,
                evaluation_date=eval_date,
                subset=(entry.get("dataset_id") or "").lower() or None,
                source_id=source_id,
                trust_tier=TrustTier.A,
                evaluation_notes=". ".join(note_parts),
            )
        except Exception as e:
            self.log_warning(f"Failed to parse entry: {e}")
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


class ARCAGI2Ingestor(BaseIngestor):
    """Ingestor for ARC-AGI 2.

    Data source: ARC Prize leaderboard (official) with snapshot fallback.
    ARC-AGI 2 is a harder benchmark with improved evaluation methodology.

    Note: ARC-AGI 2 data is not available from Epoch AI.
    """

    BENCHMARK_ID = "arc_agi_2"
    LEADERBOARD_URL = "https://arcprize.org/leaderboard"
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "scraped"
    CLEAR_EXISTING_RESULTS = True

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
        notes="Scores from ARC Prize leaderboard (official), preferring ARC-AGI 2 semi-private split when available.",
    )

    def fetch_raw(self) -> Path:
        """Fetch ARC-AGI 2 data from ARC Prize leaderboard."""
        try:
            return get_arcprize_snapshot()
        except Exception as e:
            self.log_warning(f"ARC Prize fetch failed: {e}")

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
        results = []

        # Handle JSON format
        if raw_path.suffix == ".json":
            try:
                data = load_arcprize_snapshot(raw_path)
                entries = data.get("benchmarks", {}).get(self.BENCHMARK_ID, [])
                source = Source(
                    source_id=self.generate_source_id(data.get("source_url", self.LEADERBOARD_URL) + "/v2"),
                    source_type=SourceType.OFFICIAL_LEADERBOARD,
                    source_title="ARC Prize 2 Leaderboard",
                    source_url=data.get("source_url", self.LEADERBOARD_URL),
                    retrieved_at=datetime.utcnow(),
                    parse_method=_map_parse_method(data.get("parse_method")),
                    raw_snapshot_path=str(raw_path),
                )
                self.register_source(source)

                for entry in entries:
                    result = self._parse_arcprize_entry(entry, source.source_id)
                    if result:
                        results.append(result)
            except (json.JSONDecodeError, KeyError) as e:
                self.log_warning(f"Failed to parse JSON: {e}")

        # Handle CSV format (from snapshot)
        elif raw_path.suffix == ".csv":
            try:
                df = pl.read_csv(raw_path)
                source = Source(
                    source_id=self.generate_source_id(self.LEADERBOARD_URL + "/v2"),
                    source_type=SourceType.OFFICIAL_LEADERBOARD,
                    source_title="ARC Prize 2 Leaderboard (Snapshot)",
                    source_url=self.LEADERBOARD_URL,
                    retrieved_at=datetime.utcnow(),
                    parse_method=ParseMethod.CURATED_SNAPSHOT,
                    raw_snapshot_path=str(raw_path),
                )
                self.register_source(source)
                for row in df.iter_rows(named=True):
                    result = self._parse_csv_row(row, source.source_id)
                    if result:
                        results.append(result)
            except Exception as e:
                self.log_warning(f"Failed to parse CSV: {e}")

        return results

    def _parse_arcprize_entry(self, entry: dict, source_id: str) -> Result | None:
        """Parse a JSON leaderboard entry."""
        try:
            model_name = entry.get("model") or entry.get("name") or entry.get("Model version")
            if not model_name or not _is_valid_model_name(model_name):
                return None

            provider = entry.get("organization") or entry.get("provider") or self._infer_provider(model_name)
            raw_score = entry.get("score") or entry.get("accuracy")

            if raw_score is None:
                return None

            score = _score_to_percent(float(raw_score))
            reasoning_effort = entry.get("reasoning_effort")
            model_name = _with_effort_suffix(model_name, reasoning_effort)

            eval_date = self.parse_date(entry.get("date") or entry.get("release_date")) or _extract_date_from_name(model_name)
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
                subset=(entry.get("dataset_id") or "").lower() or None,
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
            if not model_name or not _is_valid_model_name(model_name):
                return None

            provider = row.get("provider") or row.get("Organization") or self._infer_provider(model_name)
            raw_score = row.get("score") or row.get("Score")

            if raw_score is None:
                return None

            score = _score_to_percent(float(raw_score))
            model_name = _with_effort_suffix(model_name, row.get("reasoning_effort"))

            eval_date = self.parse_date(row.get("date") or row.get("Release date")) or _extract_date_from_name(model_name)
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
                subset=(row.get("dataset_id") or row.get("datasetId") or "").lower() or None,
                source_id=source_id,
                trust_tier=TrustTier.A,
                evaluation_notes="ARC-AGI 2 official result"
                + (f". {row.get('notes')}" if row.get("notes") else ""),
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
