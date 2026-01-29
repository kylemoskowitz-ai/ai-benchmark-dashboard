# AI Benchmark Progress Dashboard — Architecture

## Overview

A **data-quality-first** dashboard for tracking AI model benchmark performance over time.
Every plotted point has full provenance; missing/unverified data is explicit.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                    │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────────┤
│ SWE-Bench   │  ARC-AGI    │   Epoch     │    METR     │   FrontierMath     │
│ Leaderboard │  Leaderboard│   API/CSVs  │   Reports   │   Papers/CSVs      │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴─────────┬──────────┘
       │             │             │             │                │
       ▼             ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER (Python)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  BaseIngestor (Abstract)                                            │    │
│  │  ├── SWEBenchIngestor                                               │    │
│  │  ├── ARCAGIIngestor                                                 │    │
│  │  ├── EpochIngestor                                                  │    │
│  │  ├── METRIngestor                                                   │    │
│  │  └── FrontierMathIngestor                                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Validation Pipeline (Pydantic)                                     │    │
│  │  • Schema validation        • Range checks (0-100 for %)            │    │
│  │  • Duplicate detection      • Date sanity (not future)              │    │
│  │  • Required provenance      • Trust tier assignment                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER (DuckDB)                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   models     │  │  benchmarks  │  │   results    │  │   sources    │    │
│  │              │  │              │  │              │  │              │    │
│  │ • model_id   │  │ • bench_id   │  │ • result_id  │  │ • source_id  │    │
│  │ • name       │  │ • name       │  │ • model_id   │  │ • source_type│    │
│  │ • provider   │  │ • category   │  │ • bench_id   │  │ • title      │    │
│  │ • family     │  │ • unit       │  │ • score      │  │ • url        │    │
│  │ • release_dt │  │ • scale_min  │  │ • stderr     │  │ • retrieved  │    │
│  │ • status     │  │ • scale_max  │  │ • source_id  │  │ • trust_tier │    │
│  │ • metadata   │  │ • higher_is  │  │ • eval_date  │  │ • parse_meth │    │
│  └──────────────┘  │   _better    │  │ • trust_tier │  │ • notes      │    │
│                    └──────────────┘  │ • notes      │  └──────────────┘    │
│                                      └──────────────┘                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  data/overrides.yml  →  Applied LAST for manual corrections          │   │
│  │  data/changelog.jsonl →  Append-only audit log of all changes        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API LAYER (FastAPI - Read Only)                    │
│                                                                             │
│  GET /api/v1/benchmarks              List all benchmarks                    │
│  GET /api/v1/benchmarks/{id}/results  Results for a benchmark               │
│  GET /api/v1/models                  List all models                        │
│  GET /api/v1/models/{id}             Model details + all results            │
│  GET /api/v1/frontier                Frontier (best-per-date) per benchmark │
│  GET /api/v1/projections/{bench_id}  Projections with uncertainty           │
│  GET /api/v1/data-quality            Coverage, missingness, trust summary   │
│  GET /api/v1/changelog               Data update history                    │
│  GET /api/v1/export/csv              Export filtered results as CSV         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DASHBOARD (Streamlit)                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Page 1: OVERVIEW                                                   │    │
│  │  • Frontier best-over-time chart (all benchmarks)                   │    │
│  │  • Key stats cards                                                  │    │
│  │  • Toggles: frontier-only, official-only, date range                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Page 2: BENCHMARK EXPLORER                                         │    │
│  │  • Select benchmark → time series by provider/family                │    │
│  │  • Filters: provider, model family, date range, trust tier          │    │
│  │  • Hover: citations + eval notes + trust tier                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Page 3: MODEL EXPLORER                                             │    │
│  │  • Select model → all results + metadata + citations                │    │
│  │  • Comparison mode: overlay multiple models                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Page 4: PROJECTIONS                                                │    │
│  │  • Method selector: Linear / Saturation-aware                       │    │
│  │  • Window selector for fitting                                      │    │
│  │  • Uncertainty bands: 80% + 95%                                     │    │
│  │  • Disclaimer banner (always visible)                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Page 5: DATA QUALITY                                               │    │
│  │  • Coverage matrix (benchmark × provider)                           │    │
│  │  • Missingness report                                               │    │
│  │  • Trust tier distribution                                          │    │
│  │  • Per-point provenance browser                                     │    │
│  │  • Changelog viewer                                                 │    │
│  │  • Last successful update timestamp                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  GLOBAL: Export CSV | Export Chart PNG | Dark/Light Mode                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Schemas (Pydantic + DuckDB)

### 1. Model

```python
class Model(BaseModel):
    model_id: str                    # Canonical ID: "{provider}:{name}:{version}"
    name: str                        # Display name: "GPT-4o"
    provider: str                    # "OpenAI", "Anthropic", "Google DeepMind"
    family: str | None               # "GPT-4", "Claude-3", "Gemini"
    release_date: date | None        # Official release date
    release_date_source: str | None  # URL or "official announcement"
    status: Literal["verified", "unverified"]  # verified = confirmed exists
    parameter_count: float | None    # In billions
    training_compute_flop: float | None
    training_compute_notes: str | None
    metadata: dict                   # Flexible extra fields
    created_at: datetime
    updated_at: datetime
```

### 2. Benchmark

```python
class Benchmark(BaseModel):
    benchmark_id: str               # "swe_bench_verified", "arc_agi", etc.
    name: str                       # Display: "SWE-Bench Verified"
    category: str                   # "coding", "reasoning", "agentic", "math"
    description: str
    unit: str                       # "percent", "score", "problems_solved"
    scale_min: float                # 0
    scale_max: float                # 100 or 1.0
    higher_is_better: bool          # True for most benchmarks
    official_url: str | None
    paper_url: str | None
    notes: str | None               # Harness versions, known issues
    created_at: datetime
```

### 3. Result (Core Data Point)

```python
class Result(BaseModel):
    result_id: str                  # UUID or deterministic hash
    model_id: str                   # FK to Model
    benchmark_id: str               # FK to Benchmark

    # Score data
    score: float | None             # NULL if unverified/missing
    score_stderr: float | None      # Standard error if available
    score_ci_low: float | None      # Confidence interval
    score_ci_high: float | None

    # Evaluation metadata
    evaluation_date: date | None    # When the eval was run
    harness_version: str | None     # e.g., "swe-bench-v1.2"
    subset: str | None              # e.g., "verified", "full", "tier_4"

    # PROVENANCE (Required)
    source_id: str                  # FK to Source
    trust_tier: Literal["A", "B", "C"]
    evaluation_notes: str | None    # Free text

    # Audit
    created_at: datetime
    updated_at: datetime
    is_override: bool               # True if from overrides.yml
```

### 4. Source (Provenance Record)

```python
class Source(BaseModel):
    source_id: str                  # UUID
    source_type: Literal[
        "official_paper",
        "official_leaderboard",
        "official_blog",
        "third_party_eval",
        "third_party_leaderboard",
        "manual_entry"
    ]
    source_title: str               # "SWE-bench Leaderboard"
    source_url: str                 # Full URL
    retrieved_at: datetime          # UTC timestamp
    parse_method: Literal[
        "api",
        "csv_download",
        "html_scrape",
        "pdf_extract",
        "manual"
    ]
    raw_snapshot_path: str | None   # "data/raw/swe_bench_2024-01-15.csv"
    notes: str | None
    created_at: datetime
```

### 5. Trust Tier Definitions

| Tier | Definition | Examples |
|------|------------|----------|
| **A** | Official/Primary | Paper by benchmark authors, official leaderboard |
| **B** | Semi-Official | Model provider's published results, Epoch AI evals |
| **C** | Third-Party | Community runs, blog posts, unverified sources |

---

## Provenance Enforcement

### At Ingestion Time

1. **Every `Result` MUST have a `source_id`** — validation fails otherwise
2. **Every `Source` MUST have**:
   - `source_url` (or "manual_entry" with notes)
   - `retrieved_at` timestamp
   - `parse_method`
3. **Trust tier auto-assignment**:
   - Official leaderboards/papers → Tier A
   - Epoch AI, model provider blogs → Tier B
   - Everything else → Tier C (can be overridden)

### In the UI

Every data point tooltip shows:
```
┌────────────────────────────────────────┐
│ GPT-4o: 33.2% ± 2.1%                   │
│ ─────────────────────                  │
│ 🏷️ Trust: A (Official)                │
│ 📅 Evaluated: 2024-11-15               │
│ 📄 Source: SWE-bench Leaderboard       │
│ 🔗 swe-bench.com/leaderboard           │
│ 📝 Harness v1.2, verified subset       │
└────────────────────────────────────────┘
```

### Missing Data Handling

- `score = NULL` → displayed as "—" or "Missing" in UI
- Model with `status = "unverified"` → greyed out, marked with ⚠️
- Charts show gaps (not interpolation) for missing data

---

## Adding a New Benchmark Ingestor

### Step 1: Create Ingestor Class

```python
# src/ingestors/new_benchmark.py

from .base import BaseIngestor
from src.models.schemas import Result, Source, Benchmark

class NewBenchmarkIngestor(BaseIngestor):
    """Ingestor for NewBenchmark dataset."""

    BENCHMARK_ID = "new_benchmark"
    BENCHMARK_META = Benchmark(
        benchmark_id="new_benchmark",
        name="New Benchmark",
        category="reasoning",
        description="Description here",
        unit="percent",
        scale_min=0,
        scale_max=100,
        higher_is_better=True,
        official_url="https://newbenchmark.org",
    )

    def fetch_raw(self) -> Path:
        """Download/retrieve raw data, save to data/raw/"""
        # Option A: Download CSV
        url = "https://newbenchmark.org/results.csv"
        raw_path = self.save_raw_snapshot(url, "new_benchmark")
        return raw_path

        # Option B: Load local snapshot
        return Path("data/snapshots/new_benchmark_2024-01.csv")

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse raw data into Result objects."""
        df = pl.read_csv(raw_path)

        # Create source record
        source = Source(
            source_id=self.generate_source_id(),
            source_type="official_leaderboard",
            source_title="New Benchmark Leaderboard",
            source_url="https://newbenchmark.org",
            retrieved_at=datetime.utcnow(),
            parse_method="csv_download",
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []
        for row in df.iter_rows(named=True):
            result = Result(
                result_id=self.generate_result_id(row),
                model_id=self.normalize_model_id(row["model"]),
                benchmark_id=self.BENCHMARK_ID,
                score=row.get("score"),
                score_stderr=row.get("stderr"),
                evaluation_date=self.parse_date(row.get("date")),
                source_id=source.source_id,
                trust_tier=self.assign_trust_tier(source),
            )
            results.append(result)

        return results

    def validate(self, results: list[Result]) -> list[Result]:
        """Run benchmark-specific validation."""
        validated = []
        for r in results:
            # Range check
            if r.score is not None and not (0 <= r.score <= 100):
                self.log_warning(f"Score out of range: {r}")
                continue
            validated.append(r)
        return validated
```

### Step 2: Register in Factory

```python
# src/ingestors/__init__.py

from .new_benchmark import NewBenchmarkIngestor

INGESTORS = {
    "swe_bench_verified": SWEBenchIngestor,
    "arc_agi": ARCAGIIngestor,
    "new_benchmark": NewBenchmarkIngestor,  # Add here
    ...
}
```

### Step 3: Add Benchmark Metadata

```yaml
# data/benchmarks.yml

new_benchmark:
  name: "New Benchmark"
  category: "reasoning"
  unit: "percent"
  scale_min: 0
  scale_max: 100
  higher_is_better: true
  official_url: "https://newbenchmark.org"
```

### Step 4: Test

```bash
# Run single ingestor
python -m src.ingestors.run --benchmark new_benchmark --dry-run

# Validate output
python -m src.ingestors.run --benchmark new_benchmark --validate-only
```

---

## Data Update Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  make update-data                                               │
│                                                                 │
│  1. Backup current DB        → data/backups/db_YYYYMMDD.duckdb │
│  2. For each ingestor:                                          │
│     a. fetch_raw()           → data/raw/{bench}_{date}.{ext}   │
│     b. parse()               → List[Result]                     │
│     c. validate()            → List[Result] (filtered)          │
│     d. deduplicate()         → Merge with existing              │
│  3. Apply overrides.yml      → Manual corrections              │
│  4. Update DuckDB            → Atomic transaction               │
│  5. Append to changelog.jsonl                                   │
│  6. Update "last_updated" metadata                              │
│                                                                 │
│  On ANY error: rollback to backup, report failure               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Projection Methods

### Method A: Linear Trend (Robust Baseline)

```python
def linear_projection(scores: pd.Series, dates: pd.Series,
                      window_months: int = 12) -> ProjectionResult:
    """
    Fit OLS on recent window, project forward.
    Returns point estimate + confidence intervals.
    """
    # Filter to window
    # Fit: score ~ days_since_start
    # Bootstrap for uncertainty (80%, 95% CI)
```

### Method B: Saturation-Aware (Logistic)

```python
def saturation_projection(scores: pd.Series, dates: pd.Series,
                          ceiling: float = 100) -> ProjectionResult:
    """
    Fit logistic growth model: score = ceiling / (1 + exp(-k*(t-t0)))
    Accounts for benchmark saturation.
    """
    # Fit logistic curve
    # MCMC or bootstrap for uncertainty
```

### Disclaimer (Always Shown)

> ⚠️ **Projection Disclaimer**: These projections assume benchmark definitions,
> harnesses, and evaluation protocols remain comparable over time. They are
> mathematical extrapolations, not forecasts of real-world AI capability.
> Past trends may not continue.

---

## File Structure

```
ai-benchmark-dashboard/
├── docker-compose.yml
├── Makefile
├── README.md
├── pyproject.toml
│
├── docs/
│   ├── ARCHITECTURE.md          # This file
│   └── ADDING_BENCHMARKS.md
│
├── data/
│   ├── raw/                     # Downloaded snapshots (gitignored)
│   ├── snapshots/               # Curated seed data (committed)
│   ├── processed/               # Intermediate files
│   ├── benchmark.duckdb         # Main database
│   ├── overrides.yml            # Manual corrections
│   ├── benchmarks.yml           # Benchmark metadata
│   └── changelog.jsonl          # Append-only audit log
│
├── src/
│   ├── __init__.py
│   ├── config.py                # Settings, paths, constants
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic models
│   │
│   ├── ingestors/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseIngestor ABC
│   │   ├── swe_bench.py
│   │   ├── arc_agi.py
│   │   ├── epoch.py
│   │   ├── metr.py
│   │   └── frontier_math.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py        # DuckDB connection
│   │   ├── queries.py           # Query builders
│   │   └── migrations.py        # Schema management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   └── routes.py            # Endpoint definitions
│   │
│   ├── projections/
│   │   ├── __init__.py
│   │   ├── linear.py
│   │   └── saturation.py
│   │
│   └── dashboard/
│       ├── __init__.py
│       ├── app.py               # Streamlit entry point
│       ├── pages/
│       │   ├── 1_overview.py
│       │   ├── 2_benchmark_explorer.py
│       │   ├── 3_model_explorer.py
│       │   ├── 4_projections.py
│       │   └── 5_data_quality.py
│       └── components/
│           ├── charts.py
│           ├── filters.py
│           └── tooltips.py
│
├── scripts/
│   ├── update_data.py           # Main update script
│   ├── validate_db.py           # Integrity checks
│   └── export_seed.py           # Export current DB as seed
│
└── tests/
    ├── test_schemas.py
    ├── test_ingestors.py
    └── test_projections.py
```

---

## Key Design Decisions

1. **DuckDB over SQLite/Postgres**: Fast analytics, embedded, Parquet-compatible
2. **Pydantic for validation**: Type safety, clear schemas, good error messages
3. **Streamlit over Next.js**: Faster iteration, Python-native, meets all UI requirements
4. **Append-only changelog**: Full audit trail, never lose history
5. **Overrides as separate file**: Clear separation of automated vs manual data
6. **Trust tiers**: Visual hierarchy for data confidence without hiding anything

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-29 | 1.0 | Initial architecture |
