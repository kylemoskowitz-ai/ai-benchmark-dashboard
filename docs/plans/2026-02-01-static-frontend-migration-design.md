# Static Frontend Migration Design

**Date:** 2026-02-01
**Status:** Approved
**Goal:** Replace Streamlit with a polished, static Next.js frontend that consumes pre-computed JSON artifacts from the existing Python pipeline.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER WORKFLOW                            │
│  1. Click "Run workflow" in GitHub Actions (or wait for cron)   │
│  2. Site updates automatically in ~5 minutes                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     GITHUB ACTIONS                              │
│  Run Python pipeline → Export JSON → Commit → Push              │
│  Triggers: manual button OR cron (1st and 15th of month)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLOUDFLARE PAGES                              │
│  Detects push → builds Next.js → deploys to CDN (~2 min)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LIVE SITE                                   │
│  Static HTML/JS/CSS + JSON data, fully interactive charts       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
ai-benchmark-dashboard/
├── .github/
│   └── workflows/
│       └── update-data.yml        # Cron + manual trigger
│
├── data/                          # (existing) DuckDB, cache, changelog
│   ├── benchmark.duckdb
│   ├── cache/
│   └── changelog.jsonl
│
├── src/                           # (existing) Python pipeline
│   ├── ingestors/
│   ├── db/
│   ├── models/
│   ├── projections/
│   └── export/                    # NEW
│       ├── __init__.py
│       └── generate_artifacts.py  # DuckDB → JSON
│
├── web/                           # NEW: Next.js frontend
│   ├── public/
│   │   └── data/                  # Generated JSON artifacts
│   │       ├── benchmarks.json    # Benchmark metadata
│   │       ├── results.json       # All results with provenance
│   │       ├── models.json        # Model metadata
│   │       ├── frontier.json      # Pre-computed SOTA over time
│   │       ├── projections.json   # Pre-computed forecasts
│   │       └── meta.json          # Last update, counts, version
│   │
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx         # Root layout, fonts, nav
│   │   │   ├── page.tsx           # Progress (home)
│   │   │   ├── explorer/
│   │   │   │   └── page.tsx       # Explorer page
│   │   │   └── projections/
│   │   │       └── page.tsx       # Projections page
│   │   │
│   │   ├── components/
│   │   │   ├── charts/
│   │   │   │   ├── FrontierChart.tsx
│   │   │   │   ├── BenchmarkScatter.tsx
│   │   │   │   ├── ProjectionChart.tsx
│   │   │   │   ├── ModelComparison.tsx
│   │   │   │   └── ChartTooltip.tsx
│   │   │   │
│   │   │   ├── ui/
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── DataTable.tsx
│   │   │   │   ├── MetricDisplay.tsx
│   │   │   │   ├── Select.tsx
│   │   │   │   ├── Toggle.tsx
│   │   │   │   └── Badge.tsx
│   │   │   │
│   │   │   └── layout/
│   │   │       ├── Navigation.tsx
│   │   │       ├── PageHeader.tsx
│   │   │       └── Footer.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── data.ts            # JSON loading utilities
│   │   │   └── utils.ts           # Formatting, calculations
│   │   │
│   │   └── styles/
│   │       └── globals.css
│   │
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── package.json
│   └── tsconfig.json
│
├── scripts/
│   └── update_data.py             # (existing)
│
├── Makefile
└── pyproject.toml
```

---

## JSON Artifact Schemas

### meta.json
```json
{
  "last_updated": "2026-02-01T06:00:00Z",
  "schema_version": "1.0",
  "counts": {
    "benchmarks": 10,
    "models": 150,
    "results": 2400
  }
}
```

### benchmarks.json
```json
[
  {
    "id": "swe_bench_verified",
    "name": "SWE-Bench Verified",
    "category": "Coding",
    "scale": { "min": 0, "max": 100, "unit": "%" },
    "description": "...",
    "official_url": "https://..."
  }
]
```

### results.json
```json
[
  {
    "id": "uuid",
    "benchmark_id": "swe_bench_verified",
    "model_id": "gpt-4o",
    "score": 72.5,
    "score_stderr": 1.2,
    "date": "2026-01-15",
    "trust_tier": "A",
    "source_url": "https://...",
    "source_type": "official"
  }
]
```

### models.json
```json
[
  {
    "id": "gpt-4o",
    "name": "GPT-4o",
    "provider": "OpenAI",
    "family": "GPT-4",
    "release_date": "2024-05-13",
    "parameters": null
  }
]
```

### frontier.json
```json
{
  "swe_bench_verified": [
    { "date": "2024-01-01", "score": 45.2, "model_id": "gpt-4" },
    { "date": "2024-06-01", "score": 72.5, "model_id": "gpt-4o" }
  ]
}
```

### projections.json
```json
{
  "swe_bench_verified": {
    "linear": {
      "forecast": [
        { "date": "2026-06-01", "value": 78.2, "ci_low": 74.1, "ci_high": 82.3 }
      ],
      "r_squared": 0.92
    },
    "logistic": { ... },
    "power_law": { ... }
  }
}
```

---

## GitHub Actions Workflow

```yaml
# .github/workflows/update-data.yml

name: Update Benchmark Data

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 6 1,15 * *'  # 1st and 15th of month at 6am UTC

jobs:
  update:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -e .

      - name: Run data pipeline
        run: python scripts/update_data.py

      - name: Export artifacts for web
        run: python -m src.export.generate_artifacts

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ web/public/data/
          git diff --staged --quiet || git commit -m "chore: update benchmark data $(date -u +%Y-%m-%d)"
          git push
```

---

## Design System

### Typography

**Font family:** IBM Plex (Serif, Sans, Mono)
- Headings: IBM Plex Serif Medium
- Body/UI: IBM Plex Sans Regular/Medium
- Data/Numbers: IBM Plex Mono

**Type scale (1.25 ratio):**
```css
--text-xs:    0.64rem;   /* 10px - captions, timestamps */
--text-sm:    0.8rem;    /* 13px - secondary info */
--text-base:  1rem;      /* 16px - body text */
--text-lg:    1.25rem;   /* 20px - section labels */
--text-xl:    1.563rem;  /* 25px - page titles */
--text-2xl:   1.953rem;  /* 31px - hero metrics */
--text-3xl:   2.441rem;  /* 39px - primary KPI */
```

### Color Palette

**Dark theme (primary):**
```css
--bg-primary:     #0a0a0b;
--bg-secondary:   #141416;
--bg-tertiary:    #1c1c1f;

--text-primary:   #e8e8e9;
--text-secondary: #888890;
--text-tertiary:  #555558;

--border:         #2a2a2e;
--border-focus:   #3a3a3f;

--accent:         #c9a227;  /* Muted gold */
--accent-muted:   #8b7119;
```

### Structural Motif

- Thin horizontal rules (1px) separate major sections
- No visible table cell borders — alignment creates structure
- Consistent left-edge alignment across all content
- Section headers: small, uppercase, letter-spaced (like figure captions)
- Asymmetric layouts with intentional whitespace

### Motion Rules

- Page transitions: none (instant)
- Chart data animations: 300ms ease-out
- Hover states: 150ms transitions
- Respects `prefers-reduced-motion`
- No loading spinners, skeletons, parallax, or scroll animations

### Accessibility

- WCAG AA contrast (4.5:1 minimum)
- Visible focus indicators (gold outline)
- Semantic HTML with proper landmarks
- ARIA labels on charts
- Minimum 13px font size, user-scalable

---

## Pages

### 1. Progress (Home)

**Hero section:**
- Epoch Capabilities Index as primary KPI (large display)
- Last updated timestamp
- Trend indicator

**Frontier tracking chart:**
- Multi-line time series showing best scores over time
- Benchmark toggle pills
- Optional normalization toggle

**Benchmark cards grid:**
- 4-column grid on desktop, 2 on tablet, 1 on mobile
- Current SOTA score, model, date
- Trust tier badge

**Recent records table:**
- Last 10 new records across all benchmarks
- Sortable, minimal styling

### 2. Explorer

**Mode toggle:** Benchmark view / Model view

**Benchmark view:**
- Benchmark selector dropdown
- Scatter plot: all results over time, colored by provider
- Filters: provider, date range, trust tier
- Results table below chart

**Model view:**
- Model search autocomplete
- Performance bar chart across benchmarks
- Detailed results table
- Compare mode: up to 3 models side-by-side

### 3. Projections

**Controls:**
- Benchmark selector
- Projection method toggle (Linear / Logistic / Power Law)
- Fitting window slider (6-36 months)
- Forecast horizon slider (6-36 months)

**Chart:**
- Historical data + projection with confidence intervals
- Method comparison overlay option

**Tables:**
- Model fit quality (R² scores)
- Forecast values with CI ranges

---

## Hosting: Cloudflare Pages

**Setup steps:**
1. Sign up at pages.cloudflare.com (free)
2. Connect GitHub repo
3. Configure build:
   - Build command: `cd web && npm install && npm run build`
   - Output directory: `web/out`
4. Deploy

**Features:**
- Automatic deploys on push to main
- Unlimited bandwidth (free tier)
- Global CDN
- Optional custom domain

---

## Implementation Order

1. **Python export layer** — `src/export/generate_artifacts.py`
2. **Next.js scaffold** — basic structure, routing, fonts
3. **Design system** — Tailwind config, global styles, primitives
4. **Progress page** — hero, frontier chart, benchmark cards
5. **Explorer page** — both modes with charts and tables
6. **Projections page** — controls, chart, tables
7. **GitHub Actions workflow** — CI pipeline
8. **Documentation** — hosting setup instructions

---

## Tradeoffs & Risks

| Tradeoff | Implication |
|----------|-------------|
| No server-side features | Cannot add auth, user accounts, or per-user data |
| Two stacks in one repo | Local dev requires Python + Node.js |
| UI changes need help | Structural frontend changes require assistance |
| Build time ~2 min | Acceptable for update frequency |

| Risk | Mitigation |
|------|------------|
| Epoch AI format changes | Existing ingestors handle this; export is downstream |
| Chart library limits | Recharts covers 95%; can swap to Nivo if needed |
| Cloudflare changes free tier | Easy fallback to Vercel/Netlify |

---

## Success Criteria

- [ ] Site loads in <2s on 3G connection
- [ ] All charts are interactive (hover, zoom, filter)
- [ ] Typography and color system applied consistently
- [ ] Manual workflow trigger works reliably
- [ ] Automated updates run on schedule
- [ ] Meets WCAG AA accessibility standards
