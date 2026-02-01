# AI Benchmark Progress Dashboard

A **data-quality-first** dashboard for tracking AI model benchmark performance over time.
Every plotted point has full provenance; missing/unverified data is explicit.

## Benchmarks Tracked (10 Total)

| Benchmark | Category | Source |
|-----------|----------|--------|
| Epoch Capabilities Index | General | epoch.ai |
| ARC-AGI 1 | Reasoning | arcprize.org |
| ARC-AGI 2 | Reasoning | arcprize.org |
| Humanities Last Exam | Reasoning | scale.com |
| METR Time Horizons | Agentic | metr.org |
| Remote Labor Index | Agentic | scale.com |
| ZeroBench | Multimodal | zerobench.github.io |
| MMMU | Multimodal | vals.ai |
| SWE-Bench Verified | Coding | swebench.com |
| FrontierMath (Tier 4) | Mathematics | epoch.ai

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Start the dashboard
docker compose up

# Open in browser
open http://localhost:8501
```

### Option 2: Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Initialize database with seed data
make init-db

# Start the dashboard
make run
```

## Commands

| Command | Description |
|---------|-------------|
| `make run` | Start Streamlit dashboard |
| `make update-data` | Run all ingestors, update database |
| `make update-data BENCHMARK=swe_bench` | Update single benchmark |
| `make validate` | Run data integrity checks |
| `make test` | Run test suite |
| `make export-csv` | Export database to CSV |

## Data Update

```bash
# Full update (all benchmarks)
make update-data

# Single benchmark
make update-data BENCHMARK=swe_bench_verified

# Dry run (no database changes)
make update-data DRY_RUN=1
```

The update pipeline:
1. Backs up current database
2. Fetches raw data from sources
3. Validates and transforms data
4. Applies manual overrides (`data/overrides.yml`)
5. Updates DuckDB atomically
6. Appends to changelog

**On failure**: Rolls back to backup, reports errors.

## Data Integrity

### Trust Tiers

| Tier | Meaning | Example Sources |
|------|---------|-----------------|
| **A** | Official/Primary | Benchmark authors, official leaderboard |
| **B** | Semi-Official | Model provider's results, Epoch AI |
| **C** | Third-Party | Community runs, blog posts |

### Provenance

Every data point includes:
- `source_type`: official_paper, official_leaderboard, third_party, etc.
- `source_url`: Direct link to source
- `retrieved_at`: When data was fetched
- `parse_method`: api, csv_download, html_scrape, manual
- `trust_tier`: A, B, or C

### Missing Data

- Unverified scores shown as "—" or "Missing"
- Unverified models marked with ⚠️
- Charts show gaps (no interpolation)

## Manual Overrides

Edit `data/overrides.yml` to correct data:

```yaml
overrides:
  - result_id: "abc123"
    field: "score"
    old_value: 45.2
    new_value: 46.1
    reason: "Corrected per official errata"
    date: "2024-03-15"
```

## Adding a New Benchmark

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#adding-a-new-benchmark-ingestor)

1. Create ingestor class in `src/ingestors/`
2. Register in `src/ingestors/__init__.py`
3. Add metadata to `data/benchmarks.yml`
4. Test: `make update-data BENCHMARK=new_benchmark DRY_RUN=1`

## Project Structure

```
├── data/
│   ├── benchmark.duckdb      # Main database
│   ├── overrides.yml         # Manual corrections
│   ├── changelog.jsonl       # Audit log
│   ├── raw/                  # Downloaded snapshots
│   └── snapshots/            # Seed data (committed)
├── src/
│   ├── models/               # Pydantic schemas
│   ├── ingestors/            # Data ingestors
│   ├── db/                   # Database layer
│   ├── projections/          # Trend forecasting
│   └── dashboard/            # Streamlit app
└── docs/
    └── ARCHITECTURE.md       # Full architecture docs
```

## Dashboard Pages

The dashboard uses a streamlined 4-page tab-based navigation:

1. **Progress**: Landing page with hero metrics, frontier tracking chart, and benchmark cards showing current state-of-the-art
2. **Explorer**: Unified benchmark and model exploration with filtering by provider, category, and trust tier
3. **Projections**: Mathematical forecasting with linear regression, saturation (logistic), and power law models with uncertainty visualization
4. **Admin**: Data refresh controls, quality monitoring, changelog viewer, and CSV exports

## Configuration

Environment variables (`.env`):

```bash
# Database
DATABASE_PATH=data/benchmark.duckdb

# Dashboard
STREAMLIT_PORT=8501

# Updates
UPDATE_TIMEOUT=300
BACKUP_RETENTION_DAYS=30
```

## License

MIT
