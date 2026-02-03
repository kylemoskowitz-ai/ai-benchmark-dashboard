"""Generate JSON artifacts for the static Next.js frontend.

This module reads from the DuckDB database and exports JSON files
that the frontend consumes. All data transformation happens here,
so the frontend only needs to display pre-computed data.

Output files (written to web/public/data/):
- meta.json: Last update timestamp, counts, version info
- benchmarks.json: Benchmark metadata with units and scales
- models.json: Model metadata
- results.json: All results with provenance
- frontier.json: Pre-computed SOTA over time for each benchmark
- projections.json: Pre-computed forecasts for each benchmark
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any

import polars as pl
import numpy as np

from src.db import get_connection
from src.db.queries import (
    get_all_benchmarks,
    get_all_models,
    get_results_for_benchmark,
    get_frontier_results,
)
from src.projections import linear_projection, saturation_projection, power_law_projection

logger = logging.getLogger(__name__)

# Output directory for JSON artifacts
OUTPUT_DIR = Path(__file__).parent.parent.parent / "web" / "public" / "data"


class DateEncoder(json.JSONEncoder):
    """JSON encoder that handles date/datetime objects."""

    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def write_json(data: Any, filename: str) -> Path:
    """Write data to a JSON file in the output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w") as f:
        json.dump(data, f, cls=DateEncoder, indent=2)
    logger.info(f"Wrote {filepath}")
    return filepath


class ArtifactGenerator:
    """Generates all JSON artifacts for the frontend."""

    def __init__(self):
        self.benchmarks_df: pl.DataFrame | None = None
        self.models_df: pl.DataFrame | None = None

    def generate_all(self) -> dict[str, Path]:
        """Generate all artifacts and return paths to generated files."""
        logger.info("Starting artifact generation...")

        # Load base data
        self.benchmarks_df = get_all_benchmarks()
        self.models_df = get_all_models()

        paths = {}
        paths["meta"] = self.generate_meta()
        paths["benchmarks"] = self.generate_benchmarks()
        paths["models"] = self.generate_models()
        paths["results"] = self.generate_results()
        paths["frontier"] = self.generate_frontier()
        paths["projections"] = self.generate_projections()

        logger.info(f"Generated {len(paths)} artifact files")
        return paths

    def generate_meta(self) -> Path:
        """Generate meta.json with timestamps and counts."""
        with get_connection(read_only=True) as conn:
            total_results = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            total_models = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
            total_benchmarks = conn.execute("SELECT COUNT(*) FROM benchmarks").fetchone()[0]

            # Get last update time from metadata table if it exists
            try:
                last_update = conn.execute(
                    "SELECT value FROM metadata WHERE key = 'last_update'"
                ).fetchone()
                last_update = last_update[0] if last_update else None
            except Exception:
                last_update = None

        meta = {
            "last_updated": last_update or datetime.utcnow().isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "schema_version": "1.0",
            "counts": {
                "benchmarks": total_benchmarks,
                "models": total_models,
                "results": total_results,
            },
        }

        return write_json(meta, "meta.json")

    def generate_benchmarks(self) -> Path:
        """Generate benchmarks.json with benchmark metadata and SOTA."""
        if self.benchmarks_df is None or self.benchmarks_df.is_empty():
            return write_json([], "benchmarks.json")

        benchmarks = []
        for row in self.benchmarks_df.iter_rows(named=True):
            benchmark_id = row["benchmark_id"]
            higher_is_better = row.get("higher_is_better", True)

            # Get SOTA (best result)
            sota = None
            try:
                results = get_results_for_benchmark(benchmark_id)
                if not results.is_empty():
                    results = results.filter(pl.col("score").is_not_null())
                if not results.is_empty():
                    # Sort by score (descending if higher is better)
                    sorted_results = results.sort(
                        "score",
                        descending=higher_is_better
                    )
                    best = sorted_results.row(0, named=True)
                    sota = {
                        "score": best["score"],
                        "model_id": best["model_id"],
                        "model_name": best.get("model_name", best["model_id"]),
                        "provider": best.get("provider", "Unknown"),
                        "date": best.get("evaluation_date") or best.get("model_release_date"),
                    }
            except Exception as e:
                logger.warning(f"Failed to get SOTA for {benchmark_id}: {e}")

            benchmark_data = {
                "id": benchmark_id,
                "name": row["name"],
                "category": row["category"],
                "description": row.get("description", ""),
                "unit": row.get("unit", "percent"),
                "scale": {
                    "min": row.get("scale_min", 0),
                    "max": row.get("scale_max", 100),
                },
                "higher_is_better": higher_is_better,
                "official_url": row.get("official_url"),
                "paper_url": row.get("paper_url"),
                "notes": row.get("notes"),
            }

            if sota:
                benchmark_data["sota"] = sota

            benchmarks.append(benchmark_data)

        return write_json(benchmarks, "benchmarks.json")

    def generate_models(self) -> Path:
        """Generate models.json with model metadata."""
        if self.models_df is None or self.models_df.is_empty():
            return write_json([], "models.json")

        models = []
        for row in self.models_df.iter_rows(named=True):
            models.append({
                "id": row["model_id"],
                "name": row["name"],
                "provider": row["provider"],
                "family": row.get("family"),
                "release_date": row.get("release_date"),
                "parameters": row.get("parameter_count"),
            })

        return write_json(models, "models.json")

    def generate_results(self) -> Path:
        """Generate results.json with all benchmark results."""
        results = []

        if self.benchmarks_df is None:
            return write_json([], "results.json")

        for bench_row in self.benchmarks_df.iter_rows(named=True):
            benchmark_id = bench_row["benchmark_id"]

            try:
                bench_results = get_results_for_benchmark(benchmark_id)

                for row in bench_results.iter_rows(named=True):
                    # Use evaluation_date if available, else model_release_date
                    result_date = row.get("evaluation_date") or row.get("model_release_date")

                    results.append({
                        "id": row["result_id"],
                        "benchmark_id": benchmark_id,
                        "model_id": row["model_id"],
                        "model_name": row.get("model_name", row["model_id"]),
                        "provider": row.get("provider", "Unknown"),
                        "score": row["score"],
                        "score_stderr": row.get("score_stderr"),
                        "date": result_date,
                        "trust_tier": row.get("trust_tier", "B"),
                        "source_url": row.get("source_url"),
                        "source_type": row.get("source_type"),
                    })

            except Exception as e:
                logger.warning(f"Failed to get results for {benchmark_id}: {e}")

        return write_json(results, "results.json")

    def generate_frontier(self) -> Path:
        """Generate frontier.json with SOTA progression over time."""
        frontier_data = {}

        if self.benchmarks_df is None:
            return write_json({}, "frontier.json")

        for bench_row in self.benchmarks_df.iter_rows(named=True):
            benchmark_id = bench_row["benchmark_id"]

            try:
                frontier = get_frontier_results(benchmark_id)

                if frontier.is_empty():
                    continue

                points = []
                for row in frontier.iter_rows(named=True):
                    point_date = row.get("effective_date") or row.get("evaluation_date") or row.get("model_release_date")
                    if point_date and row["score"] is not None:
                        points.append({
                            "date": point_date,
                            "score": row["score"],
                            "model_id": row["model_id"],
                            "model_name": row.get("model_name", row["model_id"]),
                            "provider": row.get("provider", "Unknown"),
                        })

                if points:
                    # Sort by date
                    points.sort(key=lambda x: x["date"] if x["date"] else "")
                    frontier_data[benchmark_id] = points

            except Exception as e:
                logger.warning(f"Failed to get frontier for {benchmark_id}: {e}")

        return write_json(frontier_data, "frontier.json")

    def generate_projections(self) -> Path:
        """Generate projections.json with pre-computed forecasts."""
        projections = {}

        if self.benchmarks_df is None:
            return write_json({}, "projections.json")

        for bench_row in self.benchmarks_df.iter_rows(named=True):
            benchmark_id = bench_row["benchmark_id"]
            unit = bench_row.get("unit", "percent")
            scale_max = bench_row.get("scale_max", 100)
            higher_is_better = bench_row.get("higher_is_better", True)

            try:
                results = get_results_for_benchmark(benchmark_id)
                if results.is_empty():
                    continue

                # Build a dense history series (daily max/min, then cumulative frontier)
                results = results.with_columns(
                    pl.coalesce(
                        pl.col("evaluation_date"),
                        pl.col("model_release_date"),
                    ).alias("effective_date")
                ).filter(pl.col("effective_date").is_not_null())

                if results.is_empty():
                    continue

                agg_expr = pl.col("score").max().alias("score") if higher_is_better else pl.col("score").min().alias("score")
                history = (
                    results
                    .group_by("effective_date")
                    .agg(agg_expr)
                    .sort("effective_date")
                )

                if higher_is_better:
                    history = history.with_columns(pl.col("score").cum_max().alias("score"))
                else:
                    history = history.with_columns(pl.col("score").cum_min().alias("score"))

                if len(history) < 8:
                    continue

                history = history.with_columns(pl.lit(benchmark_id).alias("benchmark_id"))

                history_points = [
                    {"date": row["effective_date"], "value": row["score"]}
                    for row in history.iter_rows(named=True)
                ]

                benchmark_projections = {}
                benchmark_projections["history"] = history_points

                # Linear projection
                try:
                    linear_result = linear_projection(
                        history,
                        score_col="score",
                        date_col="effective_date",
                        window_months=36,
                        forecast_months=60,
                    )
                    if linear_result:
                        linear_values = linear_result.forecast_values
                        ci_low = linear_result.ci_80_low
                        ci_high = linear_result.ci_80_high
                        if scale_max is not None:
                            linear_values = [min(v, scale_max) for v in linear_values]
                            ci_high = [min(v, scale_max) for v in ci_high]
                        benchmark_projections["linear"] = {
                            "forecast": [
                                {
                                    "date": d,
                                    "value": v,
                                    "ci_low": cl,
                                    "ci_high": ch,
                                }
                                for d, v, cl, ch in zip(
                                    linear_result.forecast_dates,
                                    linear_values,
                                    ci_low,
                                    ci_high,
                                )
                            ],
                            "r_squared": linear_result.r_squared,
                            "points_used": len(history),
                        }
                except Exception as e:
                    logger.debug(f"Linear projection failed for {benchmark_id}: {e}")

                # Logistic/saturation projection (only for percentage-based benchmarks)
                if unit == "percent" and scale_max == 100:
                    try:
                        sat_result = saturation_projection(
                            history,
                            score_col="score",
                            date_col="effective_date",
                            window_months=36,
                            forecast_months=60,
                            saturation_value=100.0,
                        )
                        if sat_result:
                            benchmark_projections["logistic"] = {
                                "forecast": [
                                    {
                                        "date": d,
                                        "value": min(v, 100),
                                        "ci_low": cl,
                                        "ci_high": min(ch, 100),
                                    }
                                    for d, v, cl, ch in zip(
                                        sat_result.forecast_dates,
                                        sat_result.forecast_values,
                                        sat_result.ci_80_low,
                                        sat_result.ci_80_high,
                                    )
                                ],
                                "r_squared": sat_result.r_squared,
                                "points_used": len(history),
                            }
                    except Exception as e:
                        logger.debug(f"Saturation projection failed for {benchmark_id}: {e}")

                # Power law projection
                try:
                    pl_result = power_law_projection(
                        history,
                        score_col="score",
                        date_col="effective_date",
                        window_months=36,
                        forecast_months=60,
                        ceiling=scale_max,
                    )
                    if pl_result:
                        forecast_values = pl_result.forecast_values
                        ci_high = pl_result.ci_80_high
                        # Cap at saturation for percentage benchmarks
                        if scale_max is not None:
                            forecast_values = [min(v, scale_max) for v in forecast_values]
                            ci_high = [min(v, scale_max) for v in ci_high]

                        benchmark_projections["power_law"] = {
                            "forecast": [
                                {
                                    "date": d,
                                    "value": v,
                                    "ci_low": cl,
                                    "ci_high": ch,
                                }
                                for d, v, cl, ch in zip(
                                    pl_result.forecast_dates,
                                    forecast_values,
                                    pl_result.ci_80_low,
                                    ci_high,
                                )
                            ],
                            "r_squared": pl_result.r_squared,
                            "points_used": len(history),
                        }
                except Exception as e:
                    logger.debug(f"Power law projection failed for {benchmark_id}: {e}")

                if benchmark_projections:
                    projections[benchmark_id] = benchmark_projections

            except Exception as e:
                logger.warning(f"Failed to generate projections for {benchmark_id}: {e}")

        return write_json(projections, "projections.json")


def generate_all_artifacts() -> dict[str, Path]:
    """Main entry point for generating all artifacts."""
    generator = ArtifactGenerator()
    return generator.generate_all()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_all_artifacts()
