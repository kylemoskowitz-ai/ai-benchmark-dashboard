"""Official SWE-Bench leaderboard ingestor.

Fetches data directly from the official swebench.com leaderboard.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class SWEBenchOfficialIngestor(BaseIngestor):
    """Ingestor for official SWE-Bench leaderboard.

    Fetches from swebench.com which contains official, verified results.
    This is the authoritative source (Tier A) for SWE-Bench scores.
    """

    BENCHMARK_ID = "swe_bench_verified"

    BENCHMARK_META = Benchmark(
        benchmark_id="swe_bench_verified",
        name="SWE-Bench Verified",
        category="coding",
        description=(
            "SWE-Bench evaluates AI models on real GitHub issues. "
            "The Verified subset contains 500 human-verified test cases."
        ),
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://www.swebench.com/",
        paper_url="https://arxiv.org/abs/2310.06770",
        notes="Official leaderboard scores from swebench.com",
    )

    LEADERBOARD_URL = "https://www.swebench.com/"

    # Model name normalization patterns
    MODEL_VARIANTS = {
        # OpenAI models with reasoning levels
        r"gpt-?5\.?2.*thinking": "GPT-5.2 Thinking",
        r"gpt-?5\.?2.*xhigh": "GPT-5.2 xHigh",
        r"gpt-?5\.?2.*high": "GPT-5.2 High",
        r"gpt-?5\.?2.*medium": "GPT-5.2 Medium",
        r"gpt-?5\.?2.*low": "GPT-5.2 Low",
        r"gpt-?5\.?2": "GPT-5.2",
        r"o3.*high": "o3 High",
        r"o3.*medium": "o3 Medium",
        r"o3.*low": "o3 Low",
        r"o3-mini.*high": "o3-mini High",
        r"o3-mini.*medium": "o3-mini Medium",
        r"o3-mini.*low": "o3-mini Low",
        # Anthropic models
        r"claude.?4\.?5.?opus": "Claude 4.5 Opus",
        r"claude.?opus.?4\.?5": "Claude 4.5 Opus",
        r"claude.?4\.?5.?sonnet": "Claude 4.5 Sonnet",
        r"claude.?sonnet.?4\.?5": "Claude 4.5 Sonnet",
        r"claude.?4.?opus": "Claude 4 Opus",
        r"claude.?opus.?4": "Claude 4 Opus",
        # Google models
        r"gemini.?3.*pro": "Gemini 3 Pro",
        r"gemini.?2.*flash": "Gemini 2 Flash",
    }

    def fetch_raw(self) -> Path:
        """Fetch the official SWE-Bench leaderboard page."""
        raw_dir = Path(__file__).parent.parent.parent / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filepath = raw_dir / f"swebench_official_{timestamp}.html"

        response = httpx.get(
            self.LEADERBOARD_URL,
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": "AI-Benchmark-Dashboard/1.0"}
        )
        response.raise_for_status()

        filepath.write_text(response.text)
        return filepath

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse the SWE-Bench leaderboard HTML."""
        html_content = raw_path.read_text()

        # Create source record
        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="SWE-Bench Official Leaderboard",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.WEB_SCRAPE,
            raw_snapshot_path=str(raw_path),
            notes="Official SWE-Bench leaderboard from swebench.com",
        )
        self.register_source(source)

        results = []

        # Try to extract embedded JSON data
        json_results = self._extract_json_data(html_content)
        if json_results:
            results.extend(self._parse_json_data(json_results, source))

        # Fall back to HTML table parsing if JSON not found
        if not results:
            results.extend(self._parse_html_table(html_content, source))

        return results

    def _extract_json_data(self, html: str) -> list[dict] | None:
        """Try to extract embedded JSON leaderboard data."""
        # Look for JSON embedded in script tags or data attributes
        patterns = [
            r'leaderboard\s*=\s*(\[.*?\]);',
            r'data\s*=\s*(\[.*?\]);',
            r'"results"\s*:\s*(\[.*?\])',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        return None

    def _parse_json_data(self, data: list[dict], source: Source) -> list[Result]:
        """Parse JSON leaderboard data."""
        results = []

        for entry in data:
            try:
                model_name_raw = entry.get("model") or entry.get("name") or ""
                if not model_name_raw:
                    continue

                # Normalize model name
                model_name = self._normalize_model_name(model_name_raw)
                provider = self._infer_provider(model_name_raw)

                # Get score
                score = entry.get("resolved_rate") or entry.get("score") or entry.get("accuracy")
                if score is None:
                    continue

                # Convert to percentage if needed
                if isinstance(score, (int, float)) and score <= 1:
                    score = score * 100

                # Create model
                model_id = self.normalize_model_id(model_name, provider)
                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    status=ModelStatus.VERIFIED,
                )
                self.register_model(model)

                # Create result
                result = Result(
                    result_id=self.generate_result_id(model_id, datetime.utcnow().date()),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=float(score),
                    evaluation_date=datetime.utcnow().date(),
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,  # Official leaderboard = Tier A
                    evaluation_notes="Official SWE-Bench leaderboard result",
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse entry: {e}")
                continue

        return results

    def _parse_html_table(self, html: str, source: Source) -> list[Result]:
        """Parse leaderboard from HTML table."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Find leaderboard table
        table = soup.find("table", class_=re.compile(r"leaderboard|results"))
        if not table:
            tables = soup.find_all("table")
            table = tables[0] if tables else None

        if not table:
            self.log_warning("Could not find leaderboard table")
            return results

        rows = table.find_all("tr")
        for row in rows[1:]:  # Skip header
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            try:
                model_name_raw = cells[0].get_text(strip=True)
                score_text = cells[1].get_text(strip=True)

                # Parse score
                score_match = re.search(r"[\d.]+", score_text)
                if not score_match:
                    continue

                score = float(score_match.group())

                # Normalize model name
                model_name = self._normalize_model_name(model_name_raw)
                provider = self._infer_provider(model_name_raw)

                # Create model
                model_id = self.normalize_model_id(model_name, provider)
                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    status=ModelStatus.VERIFIED,
                )
                self.register_model(model)

                # Create result
                result = Result(
                    result_id=self.generate_result_id(model_id, datetime.utcnow().date()),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    evaluation_date=datetime.utcnow().date(),
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,
                    evaluation_notes="Official SWE-Bench leaderboard result",
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")
                continue

        return results

    def _normalize_model_name(self, raw_name: str) -> str:
        """Normalize model name to canonical form with variant info."""
        name_lower = raw_name.lower().strip()

        # Check for known model variant patterns
        for pattern, canonical in self.MODEL_VARIANTS.items():
            if re.search(pattern, name_lower):
                return canonical

        # If no pattern matches, clean up the name
        # Remove version dates like -2025-11-12
        cleaned = re.sub(r"-\d{4}-\d{2}-\d{2}", "", raw_name)
        # Remove underscores, normalize spacing
        cleaned = re.sub(r"[_-]+", " ", cleaned).strip()

        return cleaned

    def _infer_family(self, model_name: str) -> str | None:
        """Infer model family from name."""
        name_lower = model_name.lower()

        families = {
            "GPT-5": ["gpt-5", "gpt5"],
            "GPT-4": ["gpt-4", "gpt4"],
            "o3": ["o3-", "o3 "],
            "o4": ["o4-", "o4 "],
            "Claude 4.5": ["claude 4.5", "claude-4.5", "opus 4.5", "sonnet 4.5"],
            "Claude 4": ["claude 4", "claude-4", "opus-4", "sonnet-4"],
            "Gemini 3": ["gemini 3", "gemini-3"],
            "Gemini 2": ["gemini 2", "gemini-2"],
            "DeepSeek": ["deepseek"],
            "Grok": ["grok"],
        }

        for family, patterns in families.items():
            for pattern in patterns:
                if pattern in name_lower:
                    return family

        return None

    def _infer_provider(self, model_name: str) -> str:
        """Infer provider from model name."""
        name_lower = model_name.lower()

        if any(x in name_lower for x in ["gpt", "o1", "o3", "o4", "davinci"]):
            return "OpenAI"
        if any(x in name_lower for x in ["claude", "opus", "sonnet", "haiku"]):
            return "Anthropic"
        if any(x in name_lower for x in ["gemini", "palm"]):
            return "Google"
        if "grok" in name_lower:
            return "xAI"
        if "deepseek" in name_lower:
            return "DeepSeek"
        if "qwen" in name_lower:
            return "Alibaba"
        if "llama" in name_lower:
            return "Meta"

        return "Unknown"
