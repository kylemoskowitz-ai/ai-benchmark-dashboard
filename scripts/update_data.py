#!/usr/bin/env python3
"""Data update script for benchmark dashboard.

Usage:
    python -m scripts.update_data                    # Update all benchmarks
    python -m scripts.update_data --benchmark swe_bench_verified  # Single benchmark
    python -m scripts.update_data --dry-run          # Preview without DB changes
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings, get_absolute_path, ensure_dirs
from src.db.connection import init_database, backup_database, set_last_update, get_db_path
from src.ingestors import INGESTORS, get_ingestor, get_all_ingestors
from src.models.schemas import ChangelogEntry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def append_changelog(entry: ChangelogEntry) -> None:
    """Append entry to changelog file."""
    changelog_path = get_absolute_path(settings.changelog_file)
    changelog_path.parent.mkdir(parents=True, exist_ok=True)

    with open(changelog_path, "a") as f:
        f.write(entry.to_jsonl() + "\n")


def run_update(
    benchmark_id: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the data update pipeline.

    Args:
        benchmark_id: Specific benchmark to update (None = all)
        dry_run: If True, don't write to database

    Returns:
        Summary dict with results
    """
    ensure_dirs()

    # Initialize database if needed
    if not dry_run:
        db_path = get_db_path()
        if not db_path.exists():
            logger.info("Initializing database...")
            init_database()
        else:
            # Create backup before updates
            try:
                backup_path = backup_database()
                logger.info(f"Database backed up to {backup_path}")
            except FileNotFoundError:
                logger.info("No existing database to backup")
                init_database()

    # Get ingestors to run
    if benchmark_id:
        if benchmark_id not in INGESTORS:
            logger.error(f"Unknown benchmark: {benchmark_id}")
            logger.info(f"Available benchmarks: {list(INGESTORS.keys())}")
            return {"success": False, "error": f"Unknown benchmark: {benchmark_id}"}

        ingestors = [get_ingestor(benchmark_id)]
    else:
        ingestors = get_all_ingestors()

    # Run each ingestor
    results = []
    success_count = 0
    error_count = 0

    for ingestor in ingestors:
        logger.info(f"Processing {ingestor.BENCHMARK_ID}...")

        try:
            result = ingestor.run(dry_run=dry_run)
            results.append(result)

            if result["success"]:
                success_count += 1
                logger.info(
                    f"  {ingestor.BENCHMARK_ID}: "
                    f"{result['inserted']} results inserted "
                    f"({result['validated']}/{result['parsed']} validated)"
                )

                # Log to changelog
                if not dry_run and result["inserted"] > 0:
                    entry = ChangelogEntry(
                        action="update",
                        table="results",
                        record_id=ingestor.BENCHMARK_ID,
                        new_value={"count": result["inserted"]},
                        reason=f"Batch update from {ingestor.BENCHMARK_ID} ingestor",
                        source="update_data",
                    )
                    append_changelog(entry)
            else:
                error_count += 1
                logger.error(f"  {ingestor.BENCHMARK_ID} failed: {result['errors']}")

        except Exception as e:
            error_count += 1
            logger.exception(f"  {ingestor.BENCHMARK_ID} crashed: {e}")
            results.append({
                "benchmark_id": ingestor.BENCHMARK_ID,
                "success": False,
                "errors": [str(e)],
            })

    # Update last_update timestamp
    if not dry_run and success_count > 0:
        set_last_update(datetime.utcnow())

    # Summary
    summary = {
        "success": error_count == 0,
        "total": len(ingestors),
        "succeeded": success_count,
        "failed": error_count,
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(
        f"Update complete: {success_count}/{len(ingestors)} succeeded, "
        f"{error_count} failed"
    )

    return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Update benchmark data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.update_data                    # Update all
    python -m scripts.update_data --benchmark swe_bench_verified
    python -m scripts.update_data --dry-run          # Preview only
    python -m scripts.update_data --list             # List benchmarks
        """,
    )

    parser.add_argument(
        "--benchmark", "-b",
        help="Specific benchmark to update",
        choices=list(INGESTORS.keys()),
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview without database changes",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available benchmarks",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list:
        print("Available benchmarks:")
        for benchmark_id, cls in INGESTORS.items():
            ingestor = cls()
            meta = ingestor.BENCHMARK_META
            if meta:
                print(f"  {benchmark_id}: {meta.name} ({meta.category})")
            else:
                print(f"  {benchmark_id}")
        return 0

    result = run_update(
        benchmark_id=args.benchmark,
        dry_run=args.dry_run,
    )

    # Print summary as JSON for scripting
    if args.verbose:
        print(json.dumps(result, indent=2))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
