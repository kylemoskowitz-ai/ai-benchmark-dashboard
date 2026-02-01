"""Epoch AI data fetcher - downloads and caches benchmark data from epoch.ai."""

import logging
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

EPOCH_BENCHMARK_ZIP_URL = "https://epoch.ai/data/benchmark_data.zip"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "epoch"
CACHE_EXPIRY_HOURS = 6  # Refresh cache every 6 hours


def get_epoch_data_dir(force_refresh: bool = False) -> Path:
    """Download and extract Epoch AI benchmark data.

    Downloads the benchmark_data.zip from Epoch AI, caches it locally,
    and extracts to provide CSV files for all benchmarks.

    Args:
        force_refresh: If True, re-download even if cache is fresh

    Returns:
        Path to extracted data directory containing CSV files

    Raises:
        RuntimeError: If download or extraction fails
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = CACHE_DIR / "benchmark_data.zip"
    extract_dir = CACHE_DIR / "extracted"
    timestamp_file = CACHE_DIR / ".last_download"

    # Check if cache is fresh
    cache_valid = False
    if not force_refresh and timestamp_file.exists() and extract_dir.exists():
        last_download = datetime.fromisoformat(timestamp_file.read_text().strip())
        if datetime.now() - last_download < timedelta(hours=CACHE_EXPIRY_HOURS):
            cache_valid = True
            logger.debug("Using cached Epoch data (less than %d hours old)", CACHE_EXPIRY_HOURS)

    if not cache_valid:
        logger.info("Downloading Epoch AI benchmark data from %s", EPOCH_BENCHMARK_ZIP_URL)

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(EPOCH_BENCHMARK_ZIP_URL)
                response.raise_for_status()

                zip_path.write_bytes(response.content)
                logger.info("Downloaded %d bytes", len(response.content))

        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to download Epoch data: {e}")

        # Extract ZIP
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)
            logger.info("Extracted Epoch data to %s", extract_dir)
        except zipfile.BadZipFile as e:
            raise RuntimeError(f"Failed to extract Epoch data: {e}")

        # Update timestamp
        timestamp_file.write_text(datetime.now().isoformat())

    return extract_dir


def get_epoch_csv(filename: str, force_refresh: bool = False) -> Path:
    """Get path to a specific Epoch benchmark CSV file.

    Args:
        filename: Name of the CSV file (e.g., "swe_bench_verified.csv")
        force_refresh: If True, re-download even if cache is fresh

    Returns:
        Path to the CSV file

    Raises:
        FileNotFoundError: If the CSV doesn't exist in the Epoch data
    """
    data_dir = get_epoch_data_dir(force_refresh=force_refresh)
    csv_path = data_dir / filename

    if not csv_path.exists():
        # List available files for error message
        available = [f.name for f in data_dir.glob("*.csv")]
        raise FileNotFoundError(
            f"CSV '{filename}' not found in Epoch data. "
            f"Available files: {', '.join(sorted(available)[:10])}..."
        )

    return csv_path


# Mapping from our benchmark IDs to Epoch CSV filenames
EPOCH_CSV_MAPPING = {
    "swe_bench_verified": "swe_bench_verified.csv",
    "metr_time_horizons": "metr_time_horizons_external.csv",
    "frontiermath_tier4": "frontiermath_tier_4.csv",
    "arc_agi_1": "arc_agi_external.csv",
    "arc_agi_2": "arc_agi_external.csv",  # Same file, filter by version
    "epoch_capabilities_index": "epoch_capabilities_index.csv",
    "gpqa_diamond": "gpqa_diamond.csv",
    "mmlu": "mmlu_external.csv",
    # External benchmarks not in Epoch data:
    # - zerobench (web scrape)
    # - humanities_last_exam (Scale AI)
    # - remote_labor_index (Scale AI)
    # - mmmu (vals.ai)
}


def is_epoch_benchmark(benchmark_id: str) -> bool:
    """Check if a benchmark's data is available from Epoch."""
    return benchmark_id in EPOCH_CSV_MAPPING


def get_benchmark_csv(benchmark_id: str, force_refresh: bool = False) -> Optional[Path]:
    """Get the Epoch CSV path for a benchmark, if available.

    Args:
        benchmark_id: Our internal benchmark ID
        force_refresh: If True, re-download data

    Returns:
        Path to CSV file, or None if benchmark is not in Epoch data
    """
    if benchmark_id not in EPOCH_CSV_MAPPING:
        return None

    return get_epoch_csv(EPOCH_CSV_MAPPING[benchmark_id], force_refresh=force_refresh)
