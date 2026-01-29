#!/usr/bin/env python3
"""Initialize database with schema and seed data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ensure_dirs
from src.db.connection import init_database, get_db_path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Initialize the database."""
    ensure_dirs()

    db_path = get_db_path()
    logger.info(f"Initializing database at {db_path}")

    init_database()
    logger.info("Database initialized successfully")

    # Run initial data load
    from scripts.update_data import run_update
    logger.info("Loading seed data...")
    result = run_update(dry_run=False)

    if result["success"]:
        logger.info(f"Seed data loaded: {result['succeeded']} benchmarks")
    else:
        logger.warning(f"Some benchmarks failed to load: {result['failed']}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
