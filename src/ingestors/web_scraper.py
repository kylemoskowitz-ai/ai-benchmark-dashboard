"""Web scraper for benchmark leaderboards that don't provide downloadable data.

This module scrapes data from:
- ZeroBench (zerobench.github.io)
- Scale AI leaderboards (HLE, RLI)
- MMMU (vals.ai)

Data is cached locally to avoid excessive requests.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "scraped"
CACHE_EXPIRY_HOURS = 6


def _get_cache_path(source_id: str) -> Path:
    """Get cache file path for a source."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{source_id}.json"


def _is_cache_valid(cache_path: Path) -> bool:
    """Check if cache file exists and is fresh."""
    if not cache_path.exists():
        return False

    try:
        data = json.loads(cache_path.read_text())
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        return datetime.now() - cached_at < timedelta(hours=CACHE_EXPIRY_HOURS)
    except (json.JSONDecodeError, ValueError):
        return False


def _save_cache(cache_path: Path, data: list[dict]) -> None:
    """Save scraped data to cache."""
    cache_data = {
        "cached_at": datetime.now().isoformat(),
        "data": data,
    }
    cache_path.write_text(json.dumps(cache_data, indent=2))


def _load_cache(cache_path: Path) -> list[dict]:
    """Load data from cache."""
    data = json.loads(cache_path.read_text())
    return data.get("data", [])


def scrape_zerobench(force_refresh: bool = False) -> list[dict]:
    """Scrape ZeroBench leaderboard from zerobench.github.io.

    Returns list of dicts with: model, provider, score, date
    """
    cache_path = _get_cache_path("zerobench")

    if not force_refresh and _is_cache_valid(cache_path):
        logger.debug("Using cached ZeroBench data")
        return _load_cache(cache_path)

    logger.info("Scraping ZeroBench leaderboard from zerobench.github.io")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get("https://zerobench.github.io/")
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Find the leaderboard table
        results = []

        # ZeroBench uses a table structure - look for tables
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    model_name = cells[0].get_text(strip=True)
                    score_text = cells[1].get_text(strip=True)

                    # Parse score (might have % sign)
                    score_match = re.search(r"([\d.]+)", score_text)
                    if score_match and model_name:
                        score = float(score_match.group(1))
                        provider = _infer_provider(model_name)

                        results.append({
                            "model": model_name,
                            "provider": provider,
                            "score": score,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                        })

        if results:
            _save_cache(cache_path, results)
            logger.info(f"Scraped {len(results)} entries from ZeroBench")

        return results

    except httpx.HTTPError as e:
        logger.error(f"Failed to scrape ZeroBench: {e}")
        # Return cached data if available
        if cache_path.exists():
            return _load_cache(cache_path)
        return []


def scrape_scale_leaderboard(
    leaderboard_id: str,
    force_refresh: bool = False
) -> list[dict]:
    """Scrape Scale AI leaderboard (HLE or RLI).

    Args:
        leaderboard_id: "humanitys_last_exam_text_only" or "rli"
        force_refresh: If True, re-scrape even if cache is fresh

    Returns list of dicts with: model, provider, score, date
    """
    cache_path = _get_cache_path(f"scale_{leaderboard_id}")

    if not force_refresh and _is_cache_valid(cache_path):
        logger.debug(f"Using cached Scale AI {leaderboard_id} data")
        return _load_cache(cache_path)

    url = f"https://scale.com/leaderboard/{leaderboard_id}"
    logger.info(f"Scraping Scale AI leaderboard from {url}")

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            # Scale AI might require different headers
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; BenchmarkDashboard/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            response = client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        # Scale AI uses JavaScript rendering - look for JSON data in script tags
        scripts = soup.find_all("script")
        for script in scripts:
            script_text = script.string or ""
            # Look for leaderboard data in JSON format
            if "leaderboard" in script_text.lower() or "models" in script_text.lower():
                # Try to extract JSON data
                json_match = re.search(r'\{[^{}]*"models?"[^{}]*\}', script_text)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        # Process JSON data
                        logger.debug(f"Found JSON data: {data.keys()}")
                    except json.JSONDecodeError:
                        pass

        # If no JSON, try table parsing
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    model_name = cells[0].get_text(strip=True)
                    score_text = cells[1].get_text(strip=True)

                    score_match = re.search(r"([\d.]+)", score_text)
                    if score_match and model_name:
                        score = float(score_match.group(1))
                        provider = _infer_provider(model_name)

                        results.append({
                            "model": model_name,
                            "provider": provider,
                            "score": score,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                        })

        # Also look for div-based leaderboards
        leaderboard_items = soup.find_all(class_=re.compile(r"leaderboard|rank|entry", re.I))
        for item in leaderboard_items:
            model_elem = item.find(class_=re.compile(r"model|name", re.I))
            score_elem = item.find(class_=re.compile(r"score|value", re.I))
            if model_elem and score_elem:
                model_name = model_elem.get_text(strip=True)
                score_text = score_elem.get_text(strip=True)
                score_match = re.search(r"([\d.]+)", score_text)
                if score_match and model_name:
                    score = float(score_match.group(1))
                    provider = _infer_provider(model_name)
                    results.append({
                        "model": model_name,
                        "provider": provider,
                        "score": score,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                    })

        if results:
            _save_cache(cache_path, results)
            logger.info(f"Scraped {len(results)} entries from Scale AI {leaderboard_id}")
        else:
            logger.warning(f"No data scraped from Scale AI {leaderboard_id} - site may use JS rendering")

        return results

    except httpx.HTTPError as e:
        logger.error(f"Failed to scrape Scale AI {leaderboard_id}: {e}")
        if cache_path.exists():
            return _load_cache(cache_path)
        return []


def scrape_mmmu(force_refresh: bool = False) -> list[dict]:
    """Scrape MMMU leaderboard from vals.ai.

    Returns list of dicts with: model, provider, score, date
    """
    cache_path = _get_cache_path("mmmu")

    if not force_refresh and _is_cache_valid(cache_path):
        logger.debug("Using cached MMMU data")
        return _load_cache(cache_path)

    url = "https://www.vals.ai/benchmarks/mmmu"
    logger.info(f"Scraping MMMU leaderboard from {url}")

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; BenchmarkDashboard/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            response = client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        # Look for tables
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    model_name = cells[0].get_text(strip=True)
                    score_text = cells[-1].get_text(strip=True)  # Score often last column

                    score_match = re.search(r"([\d.]+)", score_text)
                    if score_match and model_name:
                        score = float(score_match.group(1))
                        provider = _infer_provider(model_name)

                        results.append({
                            "model": model_name,
                            "provider": provider,
                            "score": score,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                        })

        if results:
            _save_cache(cache_path, results)
            logger.info(f"Scraped {len(results)} entries from MMMU")
        else:
            logger.warning("No data scraped from MMMU - site may use JS rendering")

        return results

    except httpx.HTTPError as e:
        logger.error(f"Failed to scrape MMMU: {e}")
        if cache_path.exists():
            return _load_cache(cache_path)
        return []


def _infer_provider(model_name: str) -> str:
    """Infer provider from model name."""
    name_lower = model_name.lower()

    provider_patterns = {
        "OpenAI": ["gpt", "o1", "o3", "o4", "davinci", "turbo"],
        "Anthropic": ["claude", "opus", "sonnet", "haiku"],
        "Google": ["gemini", "palm", "bard", "gemma"],
        "Meta": ["llama", "meta"],
        "Mistral": ["mistral", "mixtral"],
        "xAI": ["grok"],
        "DeepSeek": ["deepseek"],
        "Alibaba": ["qwen"],
        "Cohere": ["command", "cohere"],
        "Microsoft": ["phi"],
    }

    for provider, patterns in provider_patterns.items():
        for pattern in patterns:
            if pattern in name_lower:
                return provider

    return "Unknown"


def write_scraped_to_csv(
    source_id: str,
    data: list[dict],
    output_path: Optional[Path] = None
) -> Path:
    """Write scraped data to CSV for ingestor consumption.

    Args:
        source_id: Identifier for the data source
        data: List of dicts with model, provider, score, date
        output_path: Optional custom output path

    Returns:
        Path to the written CSV file
    """
    if output_path is None:
        output_path = CACHE_DIR / f"{source_id}_latest.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV
    lines = ["model,provider,score,date"]
    for entry in data:
        line = f"{entry['model']},{entry['provider']},{entry['score']},{entry['date']}"
        lines.append(line)

    output_path.write_text("\n".join(lines))
    logger.info(f"Wrote {len(data)} entries to {output_path}")

    return output_path
