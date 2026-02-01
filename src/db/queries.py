"""Database query functions."""

from datetime import date
from typing import Any
import polars as pl

from .connection import get_connection
from src.models.schemas import Result, Source, Model, Benchmark


def get_all_benchmarks() -> pl.DataFrame:
    """Get all benchmarks."""
    with get_connection(read_only=True) as conn:
        return conn.execute("SELECT * FROM benchmarks ORDER BY name").pl()


def get_all_models(provider: str | None = None) -> pl.DataFrame:
    """Get all models, optionally filtered by provider."""
    with get_connection(read_only=True) as conn:
        if provider:
            return conn.execute(
                "SELECT * FROM models WHERE provider = ? ORDER BY release_date DESC",
                [provider]
            ).pl()
        return conn.execute("SELECT * FROM models ORDER BY release_date DESC").pl()


def get_results_for_benchmark(
    benchmark_id: str,
    min_date: date | None = None,
    max_date: date | None = None,
    providers: list[str] | None = None,
    trust_tiers: list[str] | None = None,
    official_only: bool = False,
) -> pl.DataFrame:
    """Get results for a benchmark with filters."""
    query = """
        SELECT
            r.*,
            m.name as model_name,
            m.provider,
            m.family,
            m.release_date as model_release_date,
            s.source_type,
            s.source_title,
            s.source_url,
            s.retrieved_at
        FROM results r
        JOIN models m ON r.model_id = m.model_id
        JOIN sources s ON r.source_id = s.source_id
        WHERE r.benchmark_id = ?
    """
    params: list[Any] = [benchmark_id]

    if min_date:
        query += " AND (r.evaluation_date >= ? OR m.release_date >= ?)"
        params.extend([min_date, min_date])

    if max_date:
        query += " AND (r.evaluation_date <= ? OR m.release_date <= ?)"
        params.extend([max_date, max_date])

    if providers:
        placeholders = ",".join(["?" for _ in providers])
        query += f" AND m.provider IN ({placeholders})"
        params.extend(providers)

    if trust_tiers:
        placeholders = ",".join(["?" for _ in trust_tiers])
        query += f" AND r.trust_tier IN ({placeholders})"
        params.extend(trust_tiers)

    if official_only:
        query += " AND r.trust_tier = 'A'"

    query += " ORDER BY COALESCE(r.evaluation_date, m.release_date) ASC"

    with get_connection(read_only=True) as conn:
        return conn.execute(query, params).pl()


def get_results_for_model(model_id: str) -> pl.DataFrame:
    """Get all results for a specific model."""
    with get_connection(read_only=True) as conn:
        return conn.execute("""
            SELECT
                r.*,
                b.name as benchmark_name,
                b.category,
                b.unit,
                b.scale_max,
                b.higher_is_better,
                s.source_type,
                s.source_title,
                s.source_url,
                s.retrieved_at
            FROM results r
            JOIN benchmarks b ON r.benchmark_id = b.benchmark_id
            JOIN sources s ON r.source_id = s.source_id
            WHERE r.model_id = ?
            ORDER BY b.name
        """, [model_id]).pl()


def get_frontier_results(
    benchmark_id: str,
    min_date: date | None = None,
    trust_tiers: list[str] | None = None,
) -> pl.DataFrame:
    """Get frontier (best-over-time) results for a benchmark.

    Returns the best score for each date, creating a monotonic frontier.
    """
    # First get all results
    results = get_results_for_benchmark(
        benchmark_id,
        min_date=min_date,
        trust_tiers=trust_tiers,
    )

    if results.is_empty():
        return results

    # Get benchmark info to know if higher is better
    with get_connection(read_only=True) as conn:
        bench_info = conn.execute(
            "SELECT higher_is_better FROM benchmarks WHERE benchmark_id = ?",
            [benchmark_id]
        ).fetchone()

    higher_is_better = bench_info[0] if bench_info else True

    # Calculate frontier
    # Use release_date as the date for frontier calculation
    results = results.with_columns([
        pl.coalesce(pl.col("evaluation_date"), pl.col("model_release_date")).alias("effective_date")
    ])

    # Sort by date and calculate running max/min
    results = results.sort("effective_date")

    if higher_is_better:
        results = results.with_columns([
            pl.col("score").cum_max().alias("frontier_score")
        ])
    else:
        results = results.with_columns([
            pl.col("score").cum_min().alias("frontier_score")
        ])

    # Keep only rows where score equals frontier (i.e., new records)
    frontier = results.filter(pl.col("score") == pl.col("frontier_score"))

    return frontier


def get_data_quality_summary() -> dict[str, Any]:
    """Get summary of data quality metrics."""
    with get_connection(read_only=True) as conn:
        # Total counts
        total_results = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        total_models = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        total_benchmarks = conn.execute("SELECT COUNT(*) FROM benchmarks").fetchone()[0]

        # Trust tier distribution
        trust_dist = conn.execute("""
            SELECT trust_tier, COUNT(*) as count
            FROM results
            GROUP BY trust_tier
            ORDER BY trust_tier
        """).pl()

        # Missing scores
        missing_scores = conn.execute("""
            SELECT COUNT(*) FROM results WHERE score IS NULL
        """).fetchone()[0]

        # Coverage by benchmark
        coverage = conn.execute("""
            SELECT
                b.benchmark_id,
                b.name,
                COUNT(DISTINCT r.model_id) as model_count,
                COUNT(r.result_id) as result_count,
                COUNT(CASE WHEN r.score IS NOT NULL THEN 1 END) as valid_scores
            FROM benchmarks b
            LEFT JOIN results r ON b.benchmark_id = r.benchmark_id
            GROUP BY b.benchmark_id, b.name
        """).pl()

        # Coverage by provider
        provider_coverage = conn.execute("""
            SELECT
                m.provider,
                COUNT(DISTINCT m.model_id) as model_count,
                COUNT(r.result_id) as result_count
            FROM models m
            LEFT JOIN results r ON m.model_id = r.model_id
            GROUP BY m.provider
            ORDER BY model_count DESC
        """).pl()

        return {
            "total_results": total_results,
            "total_models": total_models,
            "total_benchmarks": total_benchmarks,
            "missing_scores": missing_scores,
            "missing_score_pct": (missing_scores / total_results * 100) if total_results > 0 else 0,
            "trust_distribution": trust_dist,
            "benchmark_coverage": coverage,
            "provider_coverage": provider_coverage,
        }


def get_all_sources() -> pl.DataFrame:
    """Get all data sources."""
    with get_connection(read_only=True) as conn:
        return conn.execute("""
            SELECT
                s.source_id,
                s.source_type,
                s.source_title,
                s.source_url,
                s.retrieved_at,
                s.parse_method,
                s.raw_snapshot_path,
                s.notes,
                s.created_at,
                COUNT(r.result_id) as result_count
            FROM sources s
            LEFT JOIN results r ON s.source_id = r.source_id
            GROUP BY s.source_id, s.source_type, s.source_title, s.source_url,
                     s.retrieved_at, s.parse_method, s.raw_snapshot_path,
                     s.notes, s.created_at
            ORDER BY s.retrieved_at DESC
        """).pl()


def insert_source(source: Source) -> None:
    """Insert a source record."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO sources
            (source_id, source_type, source_title, source_url, retrieved_at,
             parse_method, raw_snapshot_path, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            source.source_id,
            source.source_type.value,
            source.source_title,
            source.source_url,
            source.retrieved_at,
            source.parse_method.value,
            source.raw_snapshot_path,
            source.notes,
            source.created_at,
        ])
        conn.commit()


def insert_benchmark(benchmark: Benchmark) -> None:
    """Insert a benchmark record."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO benchmarks
            (benchmark_id, name, category, description, unit, scale_min, scale_max,
             higher_is_better, official_url, paper_url, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            benchmark.benchmark_id,
            benchmark.name,
            benchmark.category,
            benchmark.description,
            benchmark.unit,
            benchmark.scale_min,
            benchmark.scale_max,
            benchmark.higher_is_better,
            benchmark.official_url,
            benchmark.paper_url,
            benchmark.notes,
            benchmark.created_at,
        ])
        conn.commit()


def insert_model(model: Model) -> None:
    """Insert a model record."""
    with get_connection() as conn:
        import json
        conn.execute("""
            INSERT OR REPLACE INTO models
            (model_id, name, provider, family, release_date, release_date_source,
             status, parameter_count, training_compute_flop, training_compute_notes,
             metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            model.model_id,
            model.name,
            model.provider,
            model.family,
            model.release_date,
            model.release_date_source,
            model.status.value,
            model.parameter_count,
            model.training_compute_flop,
            model.training_compute_notes,
            json.dumps(model.metadata),
            model.created_at,
            model.updated_at,
        ])
        conn.commit()


def insert_results(results: list[Result]) -> int:
    """Insert multiple results.

    Returns:
        Number of results inserted
    """
    if not results:
        return 0

    with get_connection() as conn:
        for result in results:
            conn.execute("""
                INSERT OR REPLACE INTO results
                (result_id, model_id, benchmark_id, score, score_stderr,
                 score_ci_low, score_ci_high, evaluation_date, harness_version,
                 subset, source_id, trust_tier, evaluation_notes,
                 created_at, updated_at, is_override)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                result.result_id,
                result.model_id,
                result.benchmark_id,
                result.score,
                result.score_stderr,
                result.score_ci_low,
                result.score_ci_high,
                result.evaluation_date,
                result.harness_version,
                result.subset,
                result.source_id,
                result.trust_tier.value,
                result.evaluation_notes,
                result.created_at,
                result.updated_at,
                result.is_override,
            ])
        conn.commit()

    return len(results)


def get_unique_providers() -> list[str]:
    """Get list of unique providers."""
    with get_connection(read_only=True) as conn:
        result = conn.execute("""
            SELECT DISTINCT provider FROM models ORDER BY provider
        """).fetchall()
        return [r[0] for r in result]


def get_unique_families() -> list[str]:
    """Get list of unique model families."""
    with get_connection(read_only=True) as conn:
        result = conn.execute("""
            SELECT DISTINCT family FROM models WHERE family IS NOT NULL ORDER BY family
        """).fetchall()
        return [r[0] for r in result]


def search_models(query: str) -> pl.DataFrame:
    """Search models by name or provider."""
    with get_connection(read_only=True) as conn:
        return conn.execute("""
            SELECT * FROM models
            WHERE LOWER(name) LIKE ? OR LOWER(provider) LIKE ?
            ORDER BY release_date DESC
        """, [f"%{query.lower()}%", f"%{query.lower()}%"]).pl()
