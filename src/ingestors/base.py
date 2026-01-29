"""Base class for benchmark data ingestors."""

from abc import ABC, abstractmethod
from datetime import datetime, date
from pathlib import Path
from typing import Any
import hashlib
import logging
import re

import httpx
import polars as pl

from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod
)
from src.config import settings, get_absolute_path

logger = logging.getLogger(__name__)


class BaseIngestor(ABC):
    """Abstract base class for benchmark data ingestors.

    Subclasses must implement:
    - BENCHMARK_ID: str
    - BENCHMARK_META: Benchmark
    - fetch_raw() -> Path
    - parse(raw_path) -> list[Result]

    Optional overrides:
    - validate(results) -> list[Result]
    - get_trust_tier(source) -> TrustTier
    """

    BENCHMARK_ID: str = ""
    BENCHMARK_META: Benchmark | None = None

    def __init__(self):
        self.sources: dict[str, Source] = {}
        self.models: dict[str, Model] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []

    @abstractmethod
    def fetch_raw(self) -> Path:
        """Fetch raw data from source.

        Returns:
            Path to raw data file (saved in data/raw/)
        """
        pass

    @abstractmethod
    def parse(self, raw_path: Path) -> list[Result]:
        """Parse raw data into Result objects.

        Args:
            raw_path: Path to raw data file

        Returns:
            List of Result objects with full provenance
        """
        pass

    def validate(self, results: list[Result]) -> list[Result]:
        """Validate results. Override for benchmark-specific validation.

        Args:
            results: List of parsed results

        Returns:
            List of validated results (invalid ones removed)
        """
        validated = []
        for r in results:
            try:
                # Basic validation
                if r.score is not None:
                    bench = self.BENCHMARK_META
                    if bench and not (bench.scale_min <= r.score <= bench.scale_max):
                        self.log_warning(
                            f"Score {r.score} out of range [{bench.scale_min}, {bench.scale_max}] "
                            f"for {r.model_id}"
                        )
                        continue

                # Ensure provenance
                if not r.source_id:
                    self.log_error(f"Missing source_id for {r.model_id}")
                    continue

                validated.append(r)
            except Exception as e:
                self.log_error(f"Validation error for {r.model_id}: {e}")

        return validated

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        """Execute the full ingestion pipeline.

        Args:
            dry_run: If True, don't write to database

        Returns:
            Summary dict with counts and any errors
        """
        logger.info(f"Starting ingestion for {self.BENCHMARK_ID}")

        # 1. Fetch raw data
        try:
            raw_path = self.fetch_raw()
            logger.info(f"Raw data saved to {raw_path}")
        except Exception as e:
            self.log_error(f"Failed to fetch raw data: {e}")
            return self._summary(0, 0, 0)

        # 2. Parse data
        try:
            results = self.parse(raw_path)
            logger.info(f"Parsed {len(results)} results")
        except Exception as e:
            self.log_error(f"Failed to parse data: {e}")
            return self._summary(0, 0, 0)

        # 3. Validate
        validated = self.validate(results)
        logger.info(f"Validated {len(validated)}/{len(results)} results")

        # 4. Write to database (unless dry run)
        if dry_run:
            logger.info("Dry run - not writing to database")
            return self._summary(len(results), len(validated), 0)

        try:
            from src.db import insert_results, insert_source, insert_model
            from src.db.queries import insert_benchmark

            # Insert benchmark metadata
            if self.BENCHMARK_META:
                insert_benchmark(self.BENCHMARK_META)

            # Insert sources
            for source in self.sources.values():
                insert_source(source)

            # Insert models
            for model in self.models.values():
                insert_model(model)

            # Insert results
            inserted = insert_results(validated)
            logger.info(f"Inserted {inserted} results")

            return self._summary(len(results), len(validated), inserted)
        except Exception as e:
            self.log_error(f"Failed to write to database: {e}")
            return self._summary(len(results), len(validated), 0)

    def _summary(self, parsed: int, validated: int, inserted: int) -> dict[str, Any]:
        """Generate summary dict."""
        return {
            "benchmark_id": self.BENCHMARK_ID,
            "parsed": parsed,
            "validated": validated,
            "inserted": inserted,
            "warnings": self.warnings,
            "errors": self.errors,
            "success": len(self.errors) == 0,
        }

    # Helper methods

    def save_raw_snapshot(self, url: str, filename_prefix: str) -> Path:
        """Download and save raw data snapshot.

        Args:
            url: URL to download
            filename_prefix: Prefix for saved file

        Returns:
            Path to saved file
        """
        raw_dir = get_absolute_path(settings.raw_data_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ext = url.split(".")[-1].split("?")[0]
        if ext not in ["csv", "json", "html"]:
            ext = "txt"

        filename = f"{filename_prefix}_{timestamp}.{ext}"
        filepath = raw_dir / filename

        response = httpx.get(url, follow_redirects=True, timeout=60)
        response.raise_for_status()

        filepath.write_bytes(response.content)
        return filepath

    def load_local_snapshot(self, filename: str) -> Path:
        """Load a pre-existing snapshot from snapshots directory.

        Args:
            filename: Name of file in data/snapshots/

        Returns:
            Path to snapshot file
        """
        snapshot_dir = get_absolute_path(settings.snapshots_dir)
        filepath = snapshot_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Snapshot not found: {filepath}")
        return filepath

    def register_source(self, source: Source) -> None:
        """Register a source for later insertion."""
        self.sources[source.source_id] = source

    def register_model(self, model: Model) -> None:
        """Register a model for later insertion."""
        self.models[model.model_id] = model

    def generate_source_id(self, url: str) -> str:
        """Generate deterministic source ID."""
        timestamp = datetime.utcnow()
        return Source.generate_id(url, timestamp)

    def generate_result_id(self, model_id: str, eval_date: date | None = None) -> str:
        """Generate deterministic result ID."""
        return Result.generate_id(model_id, self.BENCHMARK_ID, eval_date)

    def normalize_model_id(self, raw_name: str, provider: str = "") -> str:
        """Normalize model name to canonical ID format.

        Args:
            raw_name: Raw model name from source
            provider: Provider name if known

        Returns:
            Canonical model ID
        """
        # Clean up common patterns
        name = raw_name.strip()

        # Extract provider from name if not provided
        if not provider:
            provider = self._infer_provider(name)

        # Normalize
        name_clean = re.sub(r"[^a-zA-Z0-9._-]", "_", name.lower())
        provider_clean = re.sub(r"[^a-zA-Z0-9._-]", "_", provider.lower())

        return f"{provider_clean}:{name_clean}"

    def _infer_provider(self, model_name: str) -> str:
        """Infer provider from model name."""
        name_lower = model_name.lower()

        provider_patterns = {
            "OpenAI": ["gpt-", "o1-", "o3-", "o4-", "davinci", "text-"],
            "Anthropic": ["claude", "opus", "sonnet", "haiku"],
            "Google DeepMind": ["gemini", "palm", "bard"],
            "Google": ["gemini", "palm"],
            "Meta": ["llama", "codellama"],
            "Mistral": ["mistral", "mixtral"],
            "xAI": ["grok"],
            "Cohere": ["command", "cohere"],
            "DeepSeek": ["deepseek"],
            "Alibaba": ["qwen"],
        }

        for provider, patterns in provider_patterns.items():
            for pattern in patterns:
                if pattern in name_lower:
                    return provider

        return "Unknown"

    def parse_date(self, date_str: str | None) -> date | None:
        """Parse date string to date object."""
        if not date_str:
            return None

        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(date_str)[:26], fmt).date()
            except ValueError:
                continue

        self.log_warning(f"Could not parse date: {date_str}")
        return None

    def assign_trust_tier(self, source: Source) -> TrustTier:
        """Assign trust tier based on source type.

        Can be overridden for benchmark-specific logic.
        """
        if source.source_type in [
            SourceType.OFFICIAL_PAPER,
            SourceType.OFFICIAL_LEADERBOARD,
        ]:
            return TrustTier.A
        elif source.source_type in [
            SourceType.OFFICIAL_BLOG,
            SourceType.THIRD_PARTY_LEADERBOARD,
        ]:
            return TrustTier.B
        else:
            return TrustTier.C

    def log_warning(self, message: str) -> None:
        """Log a warning."""
        logger.warning(f"[{self.BENCHMARK_ID}] {message}")
        self.warnings.append(message)

    def log_error(self, message: str) -> None:
        """Log an error."""
        logger.error(f"[{self.BENCHMARK_ID}] {message}")
        self.errors.append(message)
