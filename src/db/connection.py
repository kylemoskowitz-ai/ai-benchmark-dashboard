"""DuckDB connection management."""

import duckdb
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
import shutil

from src.config import settings, get_absolute_path


def get_db_path() -> Path:
    """Get absolute path to database file."""
    return get_absolute_path(settings.database_path)


@contextmanager
def get_connection(read_only: bool = False):
    """Get a DuckDB connection.

    Args:
        read_only: If True, open in read-only mode (for concurrent reads)

    Yields:
        DuckDB connection object
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path), read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def backup_database() -> Path:
    """Create a timestamped backup of the database.

    Returns:
        Path to backup file
    """
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup_dir = get_absolute_path(settings.backups_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"benchmark_{timestamp}.duckdb"

    shutil.copy2(db_path, backup_path)
    return backup_path


def restore_database(backup_path: Path) -> None:
    """Restore database from backup.

    Args:
        backup_path: Path to backup file
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    db_path = get_db_path()
    shutil.copy2(backup_path, db_path)


def init_database() -> None:
    """Initialize database schema."""
    with get_connection() as conn:
        # Sources table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                source_id VARCHAR PRIMARY KEY,
                source_type VARCHAR NOT NULL,
                source_title VARCHAR NOT NULL,
                source_url VARCHAR NOT NULL,
                retrieved_at TIMESTAMP NOT NULL,
                parse_method VARCHAR NOT NULL,
                raw_snapshot_path VARCHAR,
                notes VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Benchmarks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS benchmarks (
                benchmark_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                category VARCHAR NOT NULL,
                description VARCHAR,
                unit VARCHAR DEFAULT 'percent',
                scale_min DOUBLE DEFAULT 0,
                scale_max DOUBLE DEFAULT 100,
                higher_is_better BOOLEAN DEFAULT TRUE,
                official_url VARCHAR,
                paper_url VARCHAR,
                notes VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Models table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                model_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                family VARCHAR,
                release_date DATE,
                release_date_source VARCHAR,
                status VARCHAR DEFAULT 'verified',
                parameter_count DOUBLE,
                training_compute_flop DOUBLE,
                training_compute_notes VARCHAR,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Results table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                result_id VARCHAR PRIMARY KEY,
                model_id VARCHAR NOT NULL REFERENCES models(model_id),
                benchmark_id VARCHAR NOT NULL REFERENCES benchmarks(benchmark_id),
                score DOUBLE,
                score_stderr DOUBLE,
                score_ci_low DOUBLE,
                score_ci_high DOUBLE,
                evaluation_date DATE,
                harness_version VARCHAR,
                subset VARCHAR,
                source_id VARCHAR NOT NULL REFERENCES sources(source_id),
                trust_tier VARCHAR NOT NULL,
                evaluation_notes VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_override BOOLEAN DEFAULT FALSE
            )
        """)

        # Metadata table for tracking updates
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key VARCHAR PRIMARY KEY,
                value VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for common queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_benchmark
            ON results(benchmark_id, evaluation_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_model
            ON results(model_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_trust
            ON results(trust_tier)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_models_provider
            ON models(provider)
        """)

        # Set initial metadata
        conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('schema_version', '1.0', CURRENT_TIMESTAMP)
        """)

        conn.commit()


def get_last_update() -> datetime | None:
    """Get timestamp of last successful data update."""
    with get_connection(read_only=True) as conn:
        result = conn.execute("""
            SELECT value FROM metadata WHERE key = 'last_update'
        """).fetchone()
        if result:
            return datetime.fromisoformat(result[0])
        return None


def set_last_update(timestamp: datetime) -> None:
    """Set timestamp of last successful data update."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_update', ?, CURRENT_TIMESTAMP)
        """, [timestamp.isoformat()])
        conn.commit()
