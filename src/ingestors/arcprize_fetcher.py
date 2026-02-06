"""ARC Prize leaderboard fetcher.

Attempts to retrieve leaderboard data from https://arcprize.org/leaderboard
by extracting embedded JSON or by probing likely JSON endpoints. Results are
normalized into a compact snapshot for ARC-AGI 1 and ARC-AGI 2 ingestors.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import httpx

logger = logging.getLogger(__name__)

ARC_PRIZE_LEADERBOARD_URL = "https://arcprize.org/leaderboard"
CANDIDATE_EVAL_URL = "https://arcprize.org/media/data/leaderboard/evaluations.json"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "arcprize"
CACHE_EXPIRY_HOURS = 6

CANDIDATE_JSON_URLS = [
    CANDIDATE_EVAL_URL,
    "https://arcprize.org/leaderboard.json",
    "https://arcprize.org/leaderboard-data.json",
    "https://arcprize.org/api/leaderboard",
    "https://arcprize.org/api/leaderboard?format=json",
    "https://arcprize.org/api/leaderboard?version=1",
    "https://arcprize.org/api/leaderboard?version=2",
]

PREFERRED_DATASET_ORDER = {
    "arc_agi_1": [
        "v1_semi_private",
        "v1_public_eval",
        "v1_private_eval",
    ],
    "arc_agi_2": [
        "v2_semi_private",
        "v2_public_eval",
        "v2_private_eval",
    ],
}

MODEL_KEYS = (
    "modelId",
    "model",
    "model_name",
    "modelName",
    "model_version",
    "Model",
    "Model version",
    "name",
    "system",
)

SCORE_KEYS = (
    "score",
    "accuracy",
    "acc",
    "percent",
    "value",
)

PROVIDER_KEYS = (
    "organization",
    "org",
    "provider",
    "team",
    "company",
)

DATE_KEYS = (
    "date",
    "release_date",
    "released",
    "timestamp",
)

NOTES_KEYS = (
    "notes",
    "method",
    "approach",
    "comment",
    "details",
)

EFFORT_KEYS = (
    "reasoning_effort",
    "effort",
    "budget",
)


def get_arcprize_snapshot(force_refresh: bool = False) -> Path:
    """Get cached ARC Prize leaderboard snapshot.

    Returns a JSON file containing normalized entries for ARC-AGI 1 and 2.
    If the cache is fresh, returns cached snapshot. If fetching fails but
    a cached snapshot exists, returns the cached snapshot with a warning.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = CACHE_DIR / "leaderboard.json"

    if not force_refresh and _cache_is_fresh(snapshot_path):
        return snapshot_path

    try:
        payload, parse_method, source_url = _fetch_payload()
        entries = _extract_entries(payload)
        grouped = _group_by_benchmark(entries)

        snapshot = {
            "retrieved_at": datetime.utcnow().isoformat(),
            "source_url": source_url,
            "parse_method": parse_method,
            "benchmarks": grouped,
        }
        snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True))
        return snapshot_path
    except Exception as exc:
        if snapshot_path.exists():
            logger.warning(
                "ARC Prize fetch failed (%s); using cached snapshot %s",
                exc,
                snapshot_path,
            )
            return snapshot_path
        raise


def load_arcprize_snapshot(snapshot_path: Path) -> dict[str, Any]:
    """Load a normalized ARC Prize snapshot from disk."""
    return json.loads(snapshot_path.read_text())


def _cache_is_fresh(snapshot_path: Path) -> bool:
    if not snapshot_path.exists():
        return False
    age = datetime.utcnow() - datetime.utcfromtimestamp(snapshot_path.stat().st_mtime)
    return age < timedelta(hours=CACHE_EXPIRY_HOURS)


def _fetch_payload() -> tuple[Any, str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ai-benchmark-dashboard/1.0)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    }

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        # Prefer explicit JSON endpoints first so we avoid scraping incidental
        # page payload objects that may contain non-leaderboard "score" fields.
        for url in CANDIDATE_JSON_URLS:
            try:
                res = client.get(url)
                if res.status_code != 200:
                    continue
                data = res.json()
                if data and _looks_like_arc_payload(data):
                    return data, "api", url
            except Exception:
                continue

        response = client.get(ARC_PRIZE_LEADERBOARD_URL)
        response.raise_for_status()
        html = response.text

        payload = _extract_json_from_html(html)
        if payload is not None and _looks_like_arc_payload(payload):
            return payload, "html_scrape", ARC_PRIZE_LEADERBOARD_URL

    raise RuntimeError("ARC Prize leaderboard payload not found")


def _looks_like_arc_payload(payload: Any) -> bool:
    if isinstance(payload, list):
        return any(
            isinstance(item, dict)
            and (
                ("datasetId" in item or "dataset_id" in item)
                and any(key in item for key in ("modelId", "model", "model_name"))
                and any(key in item for key in ("score", "accuracy", "acc"))
            )
            for item in payload
        )
    if isinstance(payload, dict):
        if isinstance(payload.get("evaluations"), list):
            return _looks_like_arc_payload(payload["evaluations"])
        if isinstance(payload.get("benchmarks"), dict):
            return True
    return _payload_has_keywords(payload)


def _extract_json_from_html(html: str) -> dict[str, Any] | None:
    # Try Next.js payload first
    match = re.search(r"__NEXT_DATA__[^>]*>(.*?)</script>", html, re.S)
    if match:
        content = html_lib.unescape(match.group(1))
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # Try other JSON script tags
    for script in re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S):
        content = html_lib.unescape(script)
        try:
            data = json.loads(content)
            if _payload_has_keywords(data):
                return data
        except json.JSONDecodeError:
            continue

    return None


def _payload_has_keywords(payload: Any) -> bool:
    keywords = ("leaderboard", "arc", "agi")
    if isinstance(payload, dict):
        for key, value in payload.items():
            if any(k in key.lower() for k in keywords):
                return True
            if _payload_has_keywords(value):
                return True
        return False
    if isinstance(payload, list):
        return any(_payload_has_keywords(item) for item in payload)
    return False


def _extract_entries(payload: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    if isinstance(payload, dict) and isinstance(payload.get("evaluations"), list):
        payload = payload["evaluations"]

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and _looks_like_entry(item):
                normalized = _normalize_entry(item, ["evaluations"])
                if normalized:
                    entries.append(normalized)
        if entries:
            return entries

    def walk(obj: Any, path: list[str]) -> None:
        if isinstance(obj, dict):
            if _looks_like_entry(obj):
                normalized = _normalize_entry(obj, path)
                if normalized:
                    entries.append(normalized)
            for key, value in obj.items():
                walk(value, path + [str(key)])
        elif isinstance(obj, list):
            for item in obj:
                walk(item, path)

    walk(payload, [])
    return entries


def _looks_like_entry(obj: dict[str, Any]) -> bool:
    keys = {str(k).lower() for k in obj.keys()}
    has_score = any(k.lower() in keys for k in SCORE_KEYS)
    has_model = any(k.lower() in keys for k in MODEL_KEYS)
    return has_score and has_model


def _normalize_entry(entry: dict[str, Any], path: Iterable[str]) -> dict[str, Any] | None:
    model = _first_value(entry, MODEL_KEYS)
    score = _parse_score(_first_value(entry, SCORE_KEYS))
    if model is None or score is None:
        return None

    display = entry.get("display")
    if display is False:
        return None

    provider = _first_value(entry, PROVIDER_KEYS)
    date = _first_value(entry, DATE_KEYS)
    notes = _first_value(entry, NOTES_KEYS)
    effort = _first_value(entry, EFFORT_KEYS)
    dataset_id = entry.get("datasetId") or entry.get("dataset_id") or entry.get("dataset")

    context = " ".join(str(p) for p in path if p)
    benchmark_hint = entry.get("benchmark") or entry.get("track") or entry.get("leaderboard")

    if not dataset_id:
        heuristic = " ".join(
            v for v in [str(benchmark_hint) if benchmark_hint else "", context, str(notes) if notes else ""]
        ).lower()
        if not re.search(r"arc[-\s]?agi|v1_|v2_|arc\s*[12]", heuristic):
            return None

    return {
        "model": str(model).strip(),
        "provider": str(provider).strip() if provider else None,
        "score": score,
        "date": str(date).strip() if date else None,
        "notes": str(notes).strip() if notes else None,
        "reasoning_effort": str(effort).strip() if effort else None,
        "dataset_id": str(dataset_id).strip() if dataset_id else None,
        "benchmark_hint": str(benchmark_hint).strip() if benchmark_hint else None,
        "context": context,
    }


def _first_value(entry: dict[str, Any], keys: Iterable[str]) -> Any | None:
    for key in keys:
        if key in entry:
            return entry.get(key)
        # Try case-insensitive match
        for existing in entry.keys():
            if str(existing).lower() == str(key).lower():
                return entry.get(existing)
    return None


def _parse_score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _group_by_benchmark(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {"arc_agi_1": [], "arc_agi_2": []}
    unclassified: list[dict[str, Any]] = []

    for entry in entries:
        benchmark_id = _infer_benchmark_id(entry)
        if benchmark_id:
            grouped[benchmark_id].append(entry)
        else:
            unclassified.append(entry)

    if unclassified and not grouped["arc_agi_1"] and not grouped["arc_agi_2"]:
        # If we couldn't infer, assume ARC-AGI 1 to avoid dropping all data.
        logger.warning("Could not infer ARC-AGI benchmark for %d entries; defaulting to ARC-AGI 1", len(unclassified))
        grouped["arc_agi_1"].extend(unclassified)
    elif unclassified:
        logger.warning("Dropped %d ARC Prize entries without benchmark metadata", len(unclassified))

    grouped = _filter_preferred_datasets(grouped)
    return grouped


def _infer_benchmark_id(entry: dict[str, Any]) -> str | None:
    haystack_parts = [
        entry.get("dataset_id"),
        entry.get("benchmark_hint"),
        entry.get("context"),
        entry.get("notes"),
    ]
    haystack = " ".join(p for p in haystack_parts if p).lower()

    if re.search(r"arc[-\s]?agi\s*2|arc[-\s]?agi-?2|arc\s*2", haystack):
        return "arc_agi_2"
    if re.search(r"arc[-\s]?agi\s*1|arc[-\s]?agi-?1|arc\s*1", haystack):
        return "arc_agi_1"

    if "v2_" in haystack:
        return "arc_agi_2"
    if "v1_" in haystack:
        return "arc_agi_1"

    # If reasoning effort is present, it's likely ARC-AGI 1.
    if entry.get("reasoning_effort"):
        return "arc_agi_1"

    return None


def _filter_preferred_datasets(grouped: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    for benchmark_id, entries in grouped.items():
        order = PREFERRED_DATASET_ORDER.get(benchmark_id)
        if not order:
            continue
        by_dataset: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            dataset = (entry.get("dataset_id") or "").lower()
            if dataset:
                by_dataset.setdefault(dataset, []).append(entry)

        for dataset_id in order:
            if dataset_id in by_dataset and by_dataset[dataset_id]:
                grouped[benchmark_id] = _dedupe_models(by_dataset[dataset_id])
                logger.info(
                    "ARC Prize %s using dataset %s (%d entries)",
                    benchmark_id,
                    dataset_id,
                    len(grouped[benchmark_id]),
                )
                break
    return grouped


def _dedupe_models(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        model = str(entry.get("model") or "").strip().lower()
        if not model:
            continue
        existing = deduped.get(model)
        if existing is None or float(entry.get("score", float("-inf"))) > float(existing.get("score", float("-inf"))):
            deduped[model] = entry
    return list(deduped.values())
