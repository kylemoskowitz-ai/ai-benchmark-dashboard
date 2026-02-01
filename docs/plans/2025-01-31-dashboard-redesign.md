# AI Benchmark Dashboard Redesign

## Overview

Complete UI redesign of the AI Benchmark Tracker dashboard. Consolidates from 5 pages to 4, expands benchmark coverage from 5 to 10, adds comprehensive data ingestion, and applies a minimalist academic visual style.

## Design Principles

- **Minimalist academic aesthetic**: Whitespace, serif headings, muted grays, research paper feel
- **Data quality first**: Every point has provenance, missing data is explicit
- **Epoch Capabilities Index as flagship**: Weighted composite headline metric
- **Model precision**: Exact model names, reasoning effort levels, release dates
- **Historical depth**: 2+ years of data where available

## Benchmarks (10 total)

| Benchmark | Category | Focus | Source |
|-----------|----------|-------|--------|
| Epoch Capabilities Index | Composite | Flagship aggregate metric | epoch.ai |
| ARC-AGI 1 | Reasoning | General reasoning | arcprize.org |
| ARC-AGI 2 | Reasoning | Advanced reasoning | arcprize.org |
| METR Time Horizons | Agentic | Autonomy, long-horizon tasks | metr.org |
| Remote Labor Index | Economic | Economic automation | - |
| ZeroBench | Multimodal | Visual reasoning | - |
| MMMU | Multimodal | Multimodal understanding | mmmu-benchmark.github.io |
| SWE-Bench Verified | Coding | Software engineering | swe-bench.com |
| FrontierMath Level 4 | Mathematics | Research-level math | epochai.org/frontiermath |
| Humanities Last Exam | Academic | Humanities knowledge (no tools) | - |

## Information Architecture

### Navigation

Horizontal top navigation (no sidebar) to maximize chart real estate:

```
◈ AI Benchmark Tracker                          Last updated: Jan 31, 2025

[Progress]    [Explorer]    [Projections]    [⚙ Admin]
```

- **Progress** (default): Narrative landing page, where AI is heading
- **Explorer**: Research tool for benchmark/model deep dives
- **Projections**: Forecasting laboratory with mathematical models
- **Admin**: Data management, refresh, provenance (de-emphasized)

Footer: "Every data point has a source. Missing data is explicit."

---

## Page 1: Progress

The flagship landing page. Tells the story of AI capability advancement.

### Hero Section

- Large Epoch Capabilities Index score with trend indicator (↑ +3.2 pts)
- Subtitle: "Weighted composite of 9 frontier benchmarks"
- 12-month sparkline trajectory

### Main Visualization

Full-width frontier progress chart:
- All benchmarks over time as lines
- Y-axis normalized to % of benchmark maximum (0-100%)
- Muted color palette: slate blues, warm grays, accent for Epoch
- Subtle markers at record-setting moments
- Hover: Model name, exact score, date, reasoning effort
- Toggle: "Show projections" overlays dashed forecast lines with CI bands

### Benchmark Cards Row

Horizontal row of 9 cards (one per benchmark, excluding Epoch hero):

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ ARC-AGI 2   │ │ METR        │ │ SWE-Bench   │ │ FrontierMath│
│ 85.2%       │ │ 72.1%       │ │ 62.4%       │ │ 31.8%       │
│ ↑ Claude 4  │ │ ↑ o3        │ │ ↑ Devin 2   │ │ ↑ o3        │
│ Jan 2025    │ │ Dec 2024    │ │ Jan 2025    │ │ Dec 2024    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

Cards show: current frontier score, leading model, date. Click navigates to Explorer.

### Recent Records Table

Last 10 record-setting results:

| Date | Benchmark | Model | Score | Δ | Source Tier |

---

## Page 2: Explorer

Unified research workbench with two modes.

### Mode Toggle

Segmented control at top:
```
[ By Benchmark ]    [ By Model ]
```

### By Benchmark Mode

**Selector**: Dropdown with all 10 benchmarks, Epoch at top

**Info line**: "Reasoning · Scale 0-100% · Higher is better · arcprize.org"

**Filters row**:
```
Provider: [All ▾]    Date: [Jan 2023] → [Today]    Trust Tier: [A] [B] [C]
```

**Main chart**: Scatter plot of ALL results over time (not just frontier), colored by provider

**Results table** (sortable):

| Date | Model | Provider | Reasoning Effort | Score ± Stderr | Tier | Source |

- Model column: exact name (e.g., "o3-2025-01-31")
- Reasoning Effort: "High", "Medium", "Low", or "—"
- Source: link to original URL
- Export CSV button

### By Model Mode

**Search**: Autocomplete search box + provider filter

**Selected model view**:
- Header: "Claude Opus 4.5 (Anthropic)" with release date, parameters
- Horizontal bar chart: % of max across all benchmarks
- Detailed table: All scores with provenance

**Comparison mode**:
- "Add to compare" button, up to 4 models
- Grouped bar chart comparing across benchmarks

---

## Page 3: Projections

Dedicated forecasting laboratory.

### Benchmark Selector

Dropdown, defaults to Epoch Capabilities Index

### Main Forecast Chart

- Historical data: solid line with markers
- Forecast region: shaded, 12-24 months forward
- Confidence intervals: 80% (darker), 95% (lighter)
- Theoretical ceiling: dashed line for benchmarks with known max

### Model Selector Panel

```
Fitting Method:
○ Linear extrapolation
○ Logistic (saturation)
○ Power law
○ Ensemble (weighted average)

Fitting Window: [12 months ▾]
Forecast Horizon: [18 months ▾]

☑ Show 80% CI
☑ Show 95% CI
☐ Show residuals
```

### Fit Diagnostics Card

```
┌──────────────────────────────┐
│ Model Fit: Power Law         │
│ R²: 0.943                    │
│ RMSE: 2.31                   │
│ AIC: 142.7                   │
│ Fitted: Jan 2023 → Jan 2025  │
└──────────────────────────────┘
```

### Time-to-Threshold Calculator

```
When will [Epoch Index ▾] reach [90 ▾]%?

Projection: August 2026
80% CI: [Apr 2026 – Feb 2027]
```

### Ensemble Comparison View

Toggle to overlay all fitting methods:

| Method | R² | RMSE | AIC | 12-mo Forecast |

### Forecast Table

Monthly projections with CI bounds, exportable

---

## Page 4: Admin

Data management hub. Functional, not flashy.

### Data Refresh Section

```
┌─────────────────────────────────────────────────────────────┐
│  Refresh Data                                               │
│                                                             │
│  [▶ Refresh All Benchmarks]                                 │
│                                                             │
│  Last refresh: Jan 31, 2025 at 14:32 UTC                    │
│  Status: All sources healthy                                │
└─────────────────────────────────────────────────────────────┘
```

When clicked, real-time progress:

```
✓ Epoch Capabilities Index    12 results
✓ ARC-AGI 1                   8 results
✓ ARC-AGI 2                   6 results
⟳ METR Time Horizons          fetching...
○ SWE-Bench Verified          pending
...
```

States:
- Success with count: "✓ ARC-AGI 2 — 6 results"
- No new data: "✓ ARC-AGI 2 — No new results"
- Error: "✗ METR — Connection timeout (retry?)"

### Coverage Overview

- Trust tier pie chart (A/B/C distribution)
- Summary stats: total results, models, benchmarks, coverage %

### Coverage Matrix

Heatmap: benchmarks × providers, color intensity = result count

### Sources Table

| Source | Type | Results | Last Retrieved | Status |

With links to original URLs

### Changelog

Recent 20 entries: timestamp, action, table, record, reason

### Export

```
[Export All Data (CSV)]    [Export Database (DuckDB)]
```

---

## Visual Design System

### Typography

- **Headings**: Serif font (e.g., Crimson Text, Source Serif Pro)
- **Body**: Clean sans-serif (e.g., Inter, IBM Plex Sans)
- **Data/Monospace**: JetBrains Mono or IBM Plex Mono for scores, dates

### Color Palette

Muted, academic:
- **Primary**: Slate blue (#4C5C78)
- **Accent**: Warm amber (#B8860B) for highlights, trends
- **Background**: Off-white (#FAFAFA)
- **Cards**: White (#FFFFFF) with subtle shadow
- **Borders**: Light gray (#E8E8E8)
- **Text**: Near-black (#1A1A1A), muted (#666666)

### Chart Colors

Subtle, distinguishable palette for benchmark lines:
- Slate blue, warm gray, muted teal, dusty rose, sage green
- Epoch Index gets the primary accent color

### Spacing

Generous whitespace:
- Page padding: 3rem horizontal, 2rem vertical
- Section spacing: 2rem between major sections
- Card padding: 1.5rem

### Components

- **Cards**: White background, 1px border, 6px radius, subtle shadow
- **Buttons**: Understated, border-style for secondary actions
- **Tables**: Clean, no heavy borders, alternating subtle row backgrounds
- **Charts**: White background, minimal gridlines (#F0F0F0)

---

## Data Ingestion Framework

### Ingestor Requirements

Each benchmark needs an ingestor that:

1. Fetches from official/authoritative source
2. Parses model names precisely (exact version, reasoning effort)
3. Captures historical data (back to Jan 2023 where available)
4. Returns structured results with full provenance
5. Reports clearly when no new data is found
6. Handles errors gracefully with specific messages

### New Ingestors Needed

| Benchmark | Source | Parse Method | Priority |
|-----------|--------|--------------|----------|
| ARC-AGI 2 | arcprize.org | HTML/API | High |
| Remote Labor Index | TBD | TBD | High |
| ZeroBench | GitHub/paper | CSV/API | Medium |
| MMMU | Official leaderboard | HTML scrape | Medium |
| Humanities Last Exam | TBD | TBD | Medium |

### Existing Ingestors (Update)

- Epoch Capabilities Index: expand historical range
- ARC-AGI 1: verify exact model name capture
- METR: ensure reasoning effort captured
- SWE-Bench Verified: working
- FrontierMath: working

### Model Name Standards

Store exact model identifiers:
- "gpt-4o-2024-08-06" not "GPT-4o"
- "claude-3-5-sonnet-20241022" not "Claude 3.5 Sonnet"
- "o3 (high)" with reasoning_effort="high" as separate field

---

## Implementation Phases

### Phase 1: Core UI Restructure
- New 4-page navigation
- Progress page with hero and cards
- Basic Explorer (benchmark mode)
- Apply academic visual styling

### Phase 2: Explorer Enhancement
- Model mode with search
- Comparison feature
- Full provenance display

### Phase 3: Projections Page
- Multiple fitting methods
- Time-to-threshold calculator
- Ensemble comparison
- Fit diagnostics

### Phase 4: Admin & Ingestion
- Refresh UI with progress
- New ingestors for missing benchmarks
- Historical data backfill
- Model name standardization

---

## Success Criteria

1. All 10 benchmarks have working ingestors
2. Historical data back to Jan 2023 for major benchmarks
3. All recent frontier models included with exact names
4. Projections show meaningful forecasts with good R² values
5. One-click refresh works with clear progress feedback
6. Visual style is clean, academic, and professional
