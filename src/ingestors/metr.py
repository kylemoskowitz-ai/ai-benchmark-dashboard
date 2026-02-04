"""METR Time Horizons benchmark ingestor."""

import json
import re
from datetime import datetime
from pathlib import Path
import polars as pl
import httpx

from .base import BaseIngestor
from .epoch_fetcher import get_epoch_csv
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class METRIngestor(BaseIngestor):
    """Ingestor for METR Time Horizons benchmark.

    METR evaluates AI models on their ability to complete long-horizon
    autonomous tasks. The "time horizon" metric indicates the task
    complexity (in hours) that a model can reliably complete.

    Data source: Epoch AI (automatically downloaded from epoch.ai)
    """

    BENCHMARK_ID = "metr_time_horizons"
    METR_URL = "https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/"
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "metr"

    BENCHMARK_META = Benchmark(
        benchmark_id="metr_time_horizons",
        name="METR Time Horizons",
        category="agentic",
        description=(
            "METR evaluates AI agents on long-horizon autonomous tasks. "
            "The P50 time horizon (in minutes) indicates the median task complexity "
            "a model can complete autonomously."
        ),
        unit="minutes",
        scale_min=0.0,
        scale_max=1000.0,  # Time horizons can be high
        higher_is_better=True,
        official_url="https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/",
        paper_url="https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/",
        notes="P50 time horizon in minutes. Higher = can complete more complex autonomous tasks. Data from METR-Horizon-v1.1.",
    )

    def fetch_raw(self) -> Path:
        """Fetch METR data from curated snapshot.

        Uses the latest METR-Horizon-v1.1 data from metr.org.
        """
        # Try live METR blog JSON (v1.1 embedded in page)
        try:
            raw = self._fetch_metr_json()
            if raw:
                return raw
        except Exception as e:
            self.log_warning(f"METR live fetch failed: {e}")

        # Use curated snapshot with v1.1 data
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "metr_time_horizons.csv"
        if snapshot_path.exists():
            return snapshot_path

        # Fallback to Epoch data (older version)
        return get_epoch_csv("metr_time_horizons_external.csv")

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse METR data into Result objects."""
        if raw_path.suffix == ".json":
            return self._parse_json(raw_path)

        return self._parse_csv(raw_path)

    def _parse_csv(self, raw_path: Path) -> list[Result]:
        df = pl.read_csv(raw_path)

        subset = "v1.0" if "external" in raw_path.name else "v1.1"

        # Create source record
        source = Source(
            source_id=self.generate_source_id("https://metr.org/time-horizons-v1.1"),
            source_type=SourceType.OFFICIAL_PAPER,
            source_title="METR Time Horizons v1.1",
            source_url=self.METR_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
            notes="METR-Horizon-v1.1 benchmark results. P50 time horizon in minutes.",
        )
        self.register_source(source)

        results = []
        for row in df.iter_rows(named=True):
            try:
                # Handle both snapshot format and Epoch format
                model_name = row.get("model") or row.get("Model version", "")
                if not model_name:
                    continue

                provider = row.get("provider") or row.get("Organization") or self._infer_provider(model_name)
                release_date = self.parse_date(row.get("date") or row.get("Release date"))

                # Create/register model
                model_id = self.normalize_model_id(model_name, provider)
                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    release_date=release_date,
                    status=ModelStatus.VERIFIED,
                )
                self.register_model(model)

                # Parse time horizon score (P50 in minutes)
                time_horizon = self._parse_float(row.get("score") or row.get("Time horizon"))

                # Parse confidence intervals
                ci_low = self._parse_float(row.get("score_ci_low") or row.get("CI_low"))
                ci_high = self._parse_float(row.get("score_ci_high") or row.get("CI_high"))

                # Additional score metrics
                avg_score = self._parse_float(row.get("avg_score") or row.get("average_score"))

                if time_horizon is None:
                    continue

                # Create result
                result = Result(
                    result_id=self.generate_result_id(model_id, release_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=time_horizon,
                    score_ci_low=ci_low,
                    score_ci_high=ci_high,
                    evaluation_date=release_date,
                    subset=subset,
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,  # METR = official
                    evaluation_notes=(
                        f"Version: {subset}. "
                        f"P50 time horizon: {time_horizon} min. "
                        f"Avg task score: {avg_score}. "
                        f"Notes: {row.get('notes', 'N/A')}"
                    ),
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")
                continue

        return results

    def _parse_json(self, raw_path: Path) -> list[Result]:
        payload = json.loads(raw_path.read_text())
        if not isinstance(payload, dict):
            return []

        source = Source(
            source_id=self.generate_source_id(self.METR_URL),
            source_type=SourceType.OFFICIAL_PAPER,
            source_title="METR Time Horizons (embedded data)",
            source_url=self.METR_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.HTML_SCRAPE,
            raw_snapshot_path=str(raw_path),
            notes="METR-Horizon-v1.1 benchmark results. P50 time horizon in minutes.",
        )
        self.register_source(source)

        results: list[Result] = []
        benchmarks = payload.get("benchmarks")
        if isinstance(benchmarks, dict):
            versioned = benchmarks
        else:
            data = payload.get("benchmark") if isinstance(payload, dict) else None
            versioned = {"v1.1": data} if isinstance(data, dict) else {}

        for version_label, data in versioned.items():
            if not isinstance(data, dict):
                continue
            results_map = data.get("results", {})
            if not isinstance(results_map, dict):
                continue
            version = self._infer_version(data.get("benchmark_name")) or version_label

            for model_key, entry in results_map.items():
                try:
                    metrics = entry.get("metrics", {}) if isinstance(entry, dict) else {}
                    p50 = metrics.get("p50_horizon_length", {}) if isinstance(metrics, dict) else {}
                    avg = metrics.get("average_score", {}) if isinstance(metrics, dict) else {}
                    time_horizon = self._parse_float(p50.get("estimate"))
                    if time_horizon is None:
                        continue

                    ci_low = self._parse_float(p50.get("ci_low"))
                    ci_high = self._parse_float(p50.get("ci_high"))
                    avg_score = self._parse_float(avg.get("estimate"))
                    is_sota = metrics.get("is_sota") if isinstance(metrics, dict) else None

                    model_name = model_key
                    provider = self._infer_provider(model_name)
                    release_date = self.parse_date(entry.get("release_date") if isinstance(entry, dict) else None)

                    model_id = self.normalize_model_id(model_name, provider)
                    model = Model(
                        model_id=model_id,
                        name=model_name,
                        provider=provider,
                        family=self._infer_family(model_name),
                        release_date=release_date,
                        status=ModelStatus.VERIFIED,
                    )
                    self.register_model(model)

                    notes = [
                        f"Version: {version}.",
                        f"P50 time horizon: {time_horizon} min.",
                        f"Avg task score: {avg_score}.",
                    ]
                    if is_sota is not None:
                        notes.append(f"SOTA: {is_sota}.")

                    result = Result(
                        result_id=self.generate_result_id(model_id, release_date),
                        model_id=model_id,
                        benchmark_id=self.BENCHMARK_ID,
                        score=time_horizon,
                        score_ci_low=ci_low,
                        score_ci_high=ci_high,
                        evaluation_date=release_date,
                        subset=version,
                        source_id=source.source_id,
                        trust_tier=TrustTier.A,
                        evaluation_notes=" ".join(notes),
                    )
                    results.append(result)
                except Exception as e:
                    self.log_warning(f"Failed to parse METR entry {model_key}: {e}")
                    continue

        return results

    def _fetch_metr_json(self) -> Path | None:
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.CACHE_DIR / "metr_time_horizons.json"

        response = httpx.get(self.METR_URL, timeout=30.0)
        response.raise_for_status()
        html = response.text

        data = self._extract_benchmark_versions(html)
        if not data:
            return None

        payload = {
            "retrieved_at": datetime.utcnow().isoformat(),
            "source_url": self.METR_URL,
            "benchmarks": data,
        }
        snapshot_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True))
        return snapshot_path

    def _extract_benchmark_versions(self, html: str) -> dict[str, dict]:
        versions: dict[str, dict] = {}
        data_v1_1 = self._extract_js_object(html, "benchmarkDataV1_1")
        if data_v1_1:
            versions["v1.1"] = data_v1_1
        data_v1 = self._extract_js_object(html, "benchmarkDataV1")
        if data_v1:
            versions["v1.0"] = data_v1
        return versions

    def _extract_js_object(self, html: str, var_name: str) -> dict | None:
        pattern = re.compile(rf"const\\s+{re.escape(var_name)}\\s*=\\s*", re.M)
        match = pattern.search(html)
        if not match:
            return None
        start = html.find("{", match.end())
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(html)):
            ch = html[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            else:
                if ch == '"':
                    in_string = True
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        blob = html[start : idx + 1]
                        try:
                            return json.loads(blob)
                        except json.JSONDecodeError:
                            return None
        return None

    def _infer_version(self, benchmark_name: str | None) -> str | None:
        if not benchmark_name:
            return None
        name = benchmark_name.lower()
        if "v1.1" in name:
            return "v1.1"
        if "v1.0" in name or "v1" in name:
            return "v1.0"
        return None
    def _infer_family(self, model_name: str) -> str | None:
        """Infer model family from name."""
        name_lower = model_name.lower()

        families = {
            "gpt-4": ["gpt-4", "gpt4"],
            "o1": ["o1-"],
            "claude-3": ["claude-3"],
            "claude-3.5": ["claude-3-5", "claude-3.5"],
            "gemini": ["gemini"],
            "grok": ["grok"],
            "llama": ["llama"],
            "deepseek": ["deepseek"],
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
