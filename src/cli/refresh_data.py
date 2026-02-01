"""CLI script to refresh benchmark data from official sources.

Usage:
    python -m src.cli.refresh_data [--benchmark BENCHMARK] [--dry-run]

Examples:
    # Refresh all benchmarks
    python -m src.cli.refresh_data

    # Refresh only SWE-Bench
    python -m src.cli.refresh_data --benchmark swe_bench_verified

    # Dry run (don't write to database)
    python -m src.cli.refresh_data --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ingestors.swe_bench_official import SWEBenchOfficialIngestor
from src.ingestors.swe_bench import SWEBenchIngestor
from src.ingestors.epoch import EpochIngestor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Registry of available ingestors
INGESTORS = {
    "swe_bench_verified": {
        "official": SWEBenchOfficialIngestor,
        "epoch": SWEBenchIngestor,
    },
    "gpqa_diamond": {
        "epoch": lambda: EpochIngestor("gpqa_diamond"),
    },
    "math_level_5": {
        "epoch": lambda: EpochIngestor("math_level_5"),
    },
    "aider_polyglot": {
        "epoch": lambda: EpochIngestor("aider_polyglot"),
    },
}


def refresh_benchmark(benchmark_id: str, dry_run: bool = False, prefer_official: bool = True) -> dict:
    """Refresh data for a specific benchmark.

    Args:
        benchmark_id: ID of benchmark to refresh
        dry_run: If True, don't write to database
        prefer_official: If True, try official sources first

    Returns:
        Summary dict with results
    """
    if benchmark_id not in INGESTORS:
        logger.error(f"Unknown benchmark: {benchmark_id}")
        return {"success": False, "error": f"Unknown benchmark: {benchmark_id}"}

    sources = INGESTORS[benchmark_id]

    # Determine order based on preference
    if prefer_official and "official" in sources:
        order = ["official", "epoch"]
    else:
        order = ["epoch", "official"]

    for source_type in order:
        if source_type not in sources:
            continue

        logger.info(f"Trying {source_type} source for {benchmark_id}...")

        try:
            ingestor_class = sources[source_type]
            if callable(ingestor_class) and not isinstance(ingestor_class, type):
                ingestor = ingestor_class()
            else:
                ingestor = ingestor_class()

            result = ingestor.run(dry_run=dry_run)

            if result["success"]:
                logger.info(
                    f"Successfully refreshed {benchmark_id} from {source_type}: "
                    f"{result['inserted']} results"
                )
                return result
            else:
                logger.warning(f"{source_type} source failed: {result.get('errors', [])}")

        except Exception as e:
            logger.warning(f"{source_type} source error: {e}")
            continue

    return {"success": False, "error": "All sources failed"}


def refresh_all(dry_run: bool = False) -> dict:
    """Refresh all benchmarks.

    Args:
        dry_run: If True, don't write to database

    Returns:
        Summary dict with results for each benchmark
    """
    results = {}

    for benchmark_id in INGESTORS.keys():
        logger.info(f"\n{'='*50}")
        logger.info(f"Refreshing {benchmark_id}")
        logger.info(f"{'='*50}")

        results[benchmark_id] = refresh_benchmark(benchmark_id, dry_run=dry_run)

    # Summary
    successful = sum(1 for r in results.values() if r.get("success"))
    total = len(results)

    logger.info(f"\n{'='*50}")
    logger.info(f"SUMMARY: {successful}/{total} benchmarks refreshed successfully")
    logger.info(f"{'='*50}")

    for benchmark_id, result in results.items():
        status = "✓" if result.get("success") else "✗"
        count = result.get("inserted", 0)
        logger.info(f"  {status} {benchmark_id}: {count} results")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Refresh benchmark data from official sources"
    )
    parser.add_argument(
        "--benchmark", "-b",
        type=str,
        help="Specific benchmark to refresh (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write to database, just fetch and parse",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available benchmarks",
    )
    parser.add_argument(
        "--epoch-only",
        action="store_true",
        help="Only use Epoch AI sources (skip official scrapers)",
    )

    args = parser.parse_args()

    if args.list:
        print("Available benchmarks:")
        for benchmark_id, sources in INGESTORS.items():
            source_list = ", ".join(sources.keys())
            print(f"  - {benchmark_id} ({source_list})")
        return

    logger.info(f"Data refresh started at {datetime.utcnow().isoformat()}")

    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be written to database")

    if args.benchmark:
        result = refresh_benchmark(
            args.benchmark,
            dry_run=args.dry_run,
            prefer_official=not args.epoch_only,
        )
        sys.exit(0 if result.get("success") else 1)
    else:
        results = refresh_all(dry_run=args.dry_run)
        successful = sum(1 for r in results.values() if r.get("success"))
        sys.exit(0 if successful > 0 else 1)


if __name__ == "__main__":
    main()
