"""Configuration settings for the benchmark dashboard."""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    database_path: str = Field(default="data/benchmark.duckdb", alias="DATABASE_PATH")
    raw_data_dir: Path = Field(default=Path("data/raw"))
    snapshots_dir: Path = Field(default=Path("data/snapshots"))
    backups_dir: Path = Field(default=Path("data/backups"))
    overrides_file: Path = Field(default=Path("data/overrides.yml"))
    changelog_file: Path = Field(default=Path("data/changelog.jsonl"))
    benchmarks_file: Path = Field(default=Path("data/benchmarks.yml"))

    # Dashboard
    streamlit_port: int = 8501

    # API
    api_port: int = 8000

    # Update settings
    update_timeout: int = 300  # seconds
    backup_retention_days: int = 30

    # Data settings
    min_date: str = "2024-01-29"  # 24 months lookback from 2026-01-29

    class Config:
        env_file = ".env"
        env_prefix = ""


# Global settings instance
settings = Settings()


def get_absolute_path(relative_path: Path | str) -> Path:
    """Convert relative path to absolute path from project root."""
    if isinstance(relative_path, str):
        relative_path = Path(relative_path)
    if relative_path.is_absolute():
        return relative_path
    return settings.project_root / relative_path


# Ensure directories exist
def ensure_dirs():
    """Create required directories if they don't exist."""
    dirs = [
        get_absolute_path(settings.raw_data_dir),
        get_absolute_path(settings.snapshots_dir),
        get_absolute_path(settings.backups_dir),
        get_absolute_path(Path("data/processed")),
        get_absolute_path(Path("exports")),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
