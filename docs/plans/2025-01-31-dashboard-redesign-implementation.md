# AI Benchmark Dashboard Redesign - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the AI Benchmark Tracker dashboard with 4 pages, 10 benchmarks, minimalist academic styling, and one-click data refresh.

**Architecture:** Streamlit dashboard with horizontal top navigation, Polars for data processing, DuckDB for storage, Plotly for visualizations. Ingestors follow BaseIngestor pattern for each benchmark source.

**Tech Stack:** Python 3.11+, Streamlit, Polars, DuckDB, Plotly, httpx, Pydantic, scipy (projections)

---

## Phase 1: Core UI Restructure

### Task 1.1: Update Streamlit Theme and Typography

**Files:**
- Modify: `.streamlit/config.toml`
- Modify: `src/dashboard/app.py:21-128` (CSS block)

**Step 1: Update Streamlit theme config**

Replace `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#4C5C78"
backgroundColor = "#FAFAFA"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#1A1A1A"
font = "serif"

[server]
headless = true
port = 8501
enableCORS = false

[browser]
gatherUsageStats = false
```

**Step 2: Run app to verify theme loads**

Run: `cd /Users/kylemoskowitz/Documents/Programming/ai-benchmark-dashboard && streamlit run src/dashboard/app.py --server.headless true &`
Expected: App starts without errors

**Step 3: Commit**

```bash
git add .streamlit/config.toml
git commit -m "style: update streamlit theme to academic palette"
```

---

### Task 1.2: Redesign Main App Layout with Top Navigation

**Files:**
- Modify: `src/dashboard/app.py` (complete rewrite)

**Step 1: Rewrite app.py with new layout**

Replace `src/dashboard/app.py` with:
```python
"""Main Streamlit dashboard application - Redesigned."""

import os
import streamlit as st
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="AI Benchmark Tracker",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Academic minimalist CSS
st.markdown("""
<style>
    /* Import serif font */
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Inter:wght@400;500;600&family=JetBrains+Mono&display=swap');

    /* Base layout */
    .block-container {
        padding: 1.5rem 3rem 2rem;
        max-width: 1200px;
    }

    /* Hide default sidebar */
    section[data-testid="stSidebar"] {
        display: none;
    }

    /* Typography */
    h1, h2, h3 {
        font-family: 'Source Serif 4', Georgia, serif !important;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: #1A1A1A;
    }
    h1 { font-size: 2rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.5rem; margin-top: 2rem; }
    h3 { font-size: 1.15rem; margin-top: 1.5rem; }

    p, li, label, .stMarkdown {
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.95rem;
        line-height: 1.6;
        color: #333;
    }

    /* Navigation bar */
    .nav-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 0;
        border-bottom: 1px solid #E8E8E8;
        margin-bottom: 2rem;
    }
    .nav-logo {
        font-family: 'Source Serif 4', Georgia, serif;
        font-size: 1.25rem;
        font-weight: 600;
        color: #1A1A1A;
    }
    .nav-links {
        display: flex;
        gap: 2rem;
    }
    .nav-link {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        color: #666;
        text-decoration: none;
        padding: 0.5rem 0;
        border-bottom: 2px solid transparent;
        transition: all 0.2s;
    }
    .nav-link:hover, .nav-link.active {
        color: #1A1A1A;
        border-bottom-color: #4C5C78;
    }
    .nav-meta {
        font-size: 0.8rem;
        color: #888;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 1rem 1.25rem;
        border-radius: 8px;
        border: 1px solid #E8E8E8;
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.75rem;
        font-weight: 600;
        color: #1A1A1A;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.75rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Cards */
    .benchmark-card {
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        border-radius: 8px;
        padding: 1.25rem;
        transition: box-shadow 0.2s;
    }
    .benchmark-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .benchmark-card h4 {
        font-family: 'Source Serif 4', serif;
        font-size: 1rem;
        margin: 0 0 0.5rem 0;
        color: #1A1A1A;
    }
    .benchmark-card .score {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.5rem;
        font-weight: 600;
        color: #4C5C78;
    }
    .benchmark-card .model {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .benchmark-card .date {
        font-size: 0.75rem;
        color: #999;
    }

    /* Tables */
    .stDataFrame {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem;
    }
    .stDataFrame th {
        background: #F8F9FA !important;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.05em;
    }

    /* Charts */
    .stPlotlyChart {
        background: #FFFFFF;
        border: 1px solid #E8E8E8;
        border-radius: 8px;
        padding: 1rem;
    }

    /* Buttons */
    .stButton > button {
        font-family: 'Inter', sans-serif !important;
        background: #FFFFFF;
        border: 1px solid #DDD;
        color: #333;
        font-size: 0.85rem;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: #F5F5F5;
        border-color: #BBB;
    }
    .stDownloadButton > button {
        background: #FFFFFF;
        border: 1px solid #DDD;
    }

    /* Select boxes */
    .stSelectbox label, .stMultiSelect label {
        font-size: 0.8rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid #E8E8E8;
        margin: 2rem 0;
    }

    /* Footer */
    .footer {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        color: #888;
        text-align: center;
        padding: 2rem 0 1rem;
        margin-top: 3rem;
        border-top: 1px solid #E8E8E8;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 1px solid #E8E8E8;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        color: #666;
        padding: 0.75rem 0;
        border-bottom: 2px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #1A1A1A;
        border-bottom-color: #4C5C78;
    }
</style>
""", unsafe_allow_html=True)


def get_database_path() -> Path:
    """Get path to database file."""
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return Path(env_path)
    return PROJECT_ROOT / "data" / "benchmark.duckdb"


def main():
    """Main dashboard application."""
    db_path = get_database_path()

    if not db_path.exists():
        st.error(f"Database not found at {db_path}")
        st.info("Run `make init-db` to initialize the database.")
        return

    # Header with navigation
    col_logo, col_nav, col_meta = st.columns([2, 6, 2])

    with col_logo:
        st.markdown("### ◈ AI Benchmark Tracker")

    with col_meta:
        try:
            from src.db.connection import get_last_update
            last_update = get_last_update()
            if last_update:
                st.caption(f"Updated {last_update.strftime('%b %d, %Y')}")
        except Exception:
            pass

    # Tab-based navigation
    tabs = st.tabs(["Progress", "Explorer", "Projections", "Admin"])

    # Import pages
    from src.dashboard.pages.progress import render_progress
    from src.dashboard.pages.explorer import render_explorer
    from src.dashboard.pages.projections import render_projections
    from src.dashboard.pages.admin import render_admin

    try:
        with tabs[0]:
            render_progress()
        with tabs[1]:
            render_explorer()
        with tabs[2]:
            render_projections()
        with tabs[3]:
            render_admin()
    except Exception as e:
        st.error("Error loading page")
        with st.expander("Details"):
            st.exception(e)

    # Footer
    st.markdown("""
    <div class="footer">
        Every data point has a source · Missing data is explicit · <a href="https://github.com/kylemoskowitz-ai/ai-benchmark-dashboard" style="color:#666;">GitHub</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/dashboard/app.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/dashboard/app.py
git commit -m "feat: redesign app layout with tab navigation and academic styling"
```

---

### Task 1.3: Create Progress Page (Landing)

**Files:**
- Create: `src/dashboard/pages/progress.py`
- Delete: `src/dashboard/pages/overview.py` (after migration)

**Step 1: Create progress.py**

Create `src/dashboard/pages/progress.py`:
```python
"""Progress page - AI capability advancement overview."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta
import polars as pl

from src.db.queries import (
    get_all_benchmarks,
    get_frontier_results,
    get_data_quality_summary,
)


# Benchmark display order and metadata
BENCHMARK_ORDER = [
    "epoch_capabilities_index",
    "arc_agi_1",
    "arc_agi_2",
    "metr_time_horizons",
    "remote_labor_index",
    "zerobench",
    "mmmu",
    "swe_bench_verified",
    "frontiermath_tier4",
    "humanities_last_exam",
]

BENCHMARK_COLORS = {
    "epoch_capabilities_index": "#4C5C78",  # Primary slate
    "arc_agi_1": "#6B8E9F",
    "arc_agi_2": "#5A7D8E",
    "metr_time_horizons": "#8B7355",
    "remote_labor_index": "#7A8B6E",
    "zerobench": "#9E7B9B",
    "mmmu": "#8E9B7A",
    "swe_bench_verified": "#7B8E9E",
    "frontiermath_tier4": "#9B8E7A",
    "humanities_last_exam": "#7E8B8E",
}


def render_progress():
    """Render the progress page."""

    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found. Run `make update-data` to load data.")
        return

    quality = get_data_quality_summary()

    # Hero section - Epoch Capabilities Index
    st.markdown("## AI Capability Progress")

    # Try to get Epoch index as hero metric
    epoch_frontier = get_frontier_results("epoch_capabilities_index", min_date=date(2024, 1, 1))

    if not epoch_frontier.is_empty():
        latest = epoch_frontier.sort("effective_date", descending=True).head(1)
        current_score = latest["score"][0]
        current_model = latest["model_name"][0]
        current_date = latest["effective_date"][0]

        # Calculate trend (compare to 30 days ago)
        month_ago = epoch_frontier.filter(
            pl.col("effective_date") <= (date.today() - timedelta(days=30))
        ).sort("effective_date", descending=True).head(1)

        delta = None
        if not month_ago.is_empty():
            delta = current_score - month_ago["score"][0]

        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

        with col1:
            st.metric(
                "Epoch Capabilities Index",
                f"{current_score:.1f}%",
                delta=f"{delta:+.1f} pts" if delta else None,
                help="Weighted composite of frontier benchmark scores"
            )
            st.caption(f"Led by {current_model} · {current_date}")

        with col2:
            st.metric("Results", f"{quality['total_results']:,}")
        with col3:
            st.metric("Models", f"{quality['total_models']:,}")
        with col4:
            st.metric("Coverage", f"{100 - quality['missing_score_pct']:.0f}%")
    else:
        # Fallback if no Epoch data
        cols = st.columns(4)
        cols[0].metric("Results", f"{quality['total_results']:,}")
        cols[1].metric("Models", f"{quality['total_models']:,}")
        cols[2].metric("Benchmarks", quality['total_benchmarks'])
        cols[3].metric("Coverage", f"{100 - quality['missing_score_pct']:.0f}%")

    st.divider()

    # Main frontier chart
    st.markdown("### Frontier Progress Over Time")

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_benchmarks = st.multiselect(
            "Benchmarks",
            options=[b for b in BENCHMARK_ORDER if b in benchmarks["benchmark_id"].to_list()],
            default=[b for b in BENCHMARK_ORDER[:5] if b in benchmarks["benchmark_id"].to_list()],
            format_func=lambda x: benchmarks.filter(pl.col("benchmark_id") == x)["name"][0]
                if x in benchmarks["benchmark_id"].to_list() else x,
        )
    with col2:
        normalize = st.checkbox("Normalize to %", value=True, help="Show all benchmarks as % of max score")

    if not selected_benchmarks:
        st.info("Select at least one benchmark to display.")
        return

    # Gather frontier data
    all_frontiers = []

    for bench_id in selected_benchmarks:
        frontier = get_frontier_results(bench_id, min_date=date(2023, 1, 1))

        if frontier.is_empty():
            continue

        bench_meta = benchmarks.filter(pl.col("benchmark_id") == bench_id)
        bench_name = bench_meta["name"][0] if len(bench_meta) > 0 else bench_id
        scale_max = bench_meta["scale_max"][0] if len(bench_meta) > 0 else 100

        frontier = frontier.with_columns([
            pl.lit(bench_id).alias("benchmark_id"),
            pl.lit(bench_name).alias("benchmark_name"),
            pl.lit(scale_max).alias("scale_max"),
        ])

        if normalize and scale_max > 0:
            frontier = frontier.with_columns([
                (pl.col("score") / scale_max * 100).alias("display_score")
            ])
        else:
            frontier = frontier.with_columns([
                pl.col("score").alias("display_score")
            ])

        all_frontiers.append(frontier)

    if not all_frontiers:
        st.warning("No frontier data found for selected benchmarks.")
        return

    combined = pl.concat(all_frontiers, how="diagonal")

    # Create chart
    fig = go.Figure()

    for bench_id in combined["benchmark_id"].unique().to_list():
        bench_data = combined.filter(pl.col("benchmark_id") == bench_id).sort("effective_date")
        bench_name = bench_data["benchmark_name"][0]
        color = BENCHMARK_COLORS.get(bench_id, "#888888")

        fig.add_trace(go.Scatter(
            x=bench_data["effective_date"].to_list(),
            y=bench_data["display_score"].to_list(),
            mode='lines+markers',
            name=bench_name,
            line=dict(width=2, color=color),
            marker=dict(size=6),
            hovertemplate=(
                f"<b>{bench_name}</b><br>"
                "Model: %{customdata[0]}<br>"
                "Score: %{y:.1f}<br>"
                "Date: %{x}<extra></extra>"
            ),
            customdata=[[m] for m in bench_data["model_name"].to_list()],
        ))

    fig.update_layout(
        xaxis_title="",
        yaxis_title="Score" + (" (%)" if normalize else ""),
        hovermode="x unified",
        height=450,
        margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11, family="Inter, sans-serif"),
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(
            gridcolor='#F0F0F0',
            showline=True,
            linecolor='#E8E8E8',
            tickfont=dict(family="Inter, sans-serif", size=11),
        ),
        yaxis=dict(
            gridcolor='#F0F0F0',
            showline=True,
            linecolor='#E8E8E8',
            tickfont=dict(family="JetBrains Mono, monospace", size=11),
        ),
        font=dict(family="Inter, sans-serif"),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Benchmark cards row
    st.markdown("### Current Frontier by Benchmark")

    # Get latest frontier for each benchmark
    cards_data = []
    for bench_id in BENCHMARK_ORDER:
        if bench_id == "epoch_capabilities_index":
            continue  # Skip - shown in hero

        frontier = get_frontier_results(bench_id, min_date=date(2024, 1, 1))
        if frontier.is_empty():
            continue

        latest = frontier.sort("effective_date", descending=True).head(1)
        bench_meta = benchmarks.filter(pl.col("benchmark_id") == bench_id)

        if bench_meta.is_empty():
            continue

        cards_data.append({
            "name": bench_meta["name"][0],
            "score": latest["score"][0],
            "scale_max": bench_meta["scale_max"][0],
            "model": latest["model_name"][0],
            "date": latest["effective_date"][0],
        })

    # Display cards in rows of 4
    for i in range(0, len(cards_data), 4):
        cols = st.columns(4)
        for j, col in enumerate(cols):
            if i + j < len(cards_data):
                card = cards_data[i + j]
                pct = (card["score"] / card["scale_max"] * 100) if card["scale_max"] > 0 else card["score"]
                with col:
                    st.markdown(f"""
                    <div class="benchmark-card">
                        <h4>{card["name"]}</h4>
                        <div class="score">{pct:.1f}%</div>
                        <div class="model">↑ {card["model"][:25]}{"..." if len(card["model"]) > 25 else ""}</div>
                        <div class="date">{card["date"]}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.divider()

    # Recent records table
    st.markdown("### Recent Records")

    recent = combined.sort("effective_date", descending=True).head(15)

    if not recent.is_empty():
        display_df = recent.select([
            "effective_date",
            "model_name",
            "benchmark_name",
            "score",
            "trust_tier",
        ]).to_pandas()

        display_df.columns = ["Date", "Model", "Benchmark", "Score", "Tier"]
        display_df["Score"] = display_df["Score"].round(2)

        st.dataframe(display_df, hide_index=True, use_container_width=True)

    # Export
    st.download_button(
        "Export Data (CSV)",
        combined.to_pandas().to_csv(index=False),
        "frontier_progress.csv",
        "text/csv",
    )
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/dashboard/pages/progress.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/dashboard/pages/progress.py
git commit -m "feat: add progress page with hero metrics and frontier chart"
```

---

### Task 1.4: Create Unified Explorer Page

**Files:**
- Create: `src/dashboard/pages/explorer.py`
- Delete later: `src/dashboard/pages/benchmark_explorer.py`, `src/dashboard/pages/model_explorer.py`

**Step 1: Create explorer.py**

Create `src/dashboard/pages/explorer.py`:
```python
"""Explorer page - unified benchmark and model exploration."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date
import polars as pl

from src.db.queries import (
    get_all_benchmarks,
    get_all_models,
    get_results_for_benchmark,
    get_results_for_model,
    get_unique_providers,
    search_models,
)


def render_explorer():
    """Render the unified explorer page."""

    st.markdown("## Explorer")

    # Mode toggle
    mode = st.radio(
        "Explore by",
        ["Benchmark", "Model"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.divider()

    if mode == "Benchmark":
        render_benchmark_mode()
    else:
        render_model_mode()


def render_benchmark_mode():
    """Render benchmark exploration mode."""

    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found.")
        return

    # Benchmark selector
    benchmark_options = {
        row["benchmark_id"]: row["name"]
        for row in benchmarks.iter_rows(named=True)
    }

    col1, col2 = st.columns([2, 3])

    with col1:
        selected_benchmark = st.selectbox(
            "Select Benchmark",
            options=list(benchmark_options.keys()),
            format_func=lambda x: benchmark_options.get(x, x),
        )

    bench_meta = benchmarks.filter(pl.col("benchmark_id") == selected_benchmark)
    if bench_meta.is_empty():
        return

    bench_info = bench_meta.row(0, named=True)

    with col2:
        st.caption(
            f"{bench_info['category'].title()} · "
            f"Scale {bench_info['scale_min']}–{bench_info['scale_max']} {bench_info['unit']} · "
            f"{'Higher is better' if bench_info['higher_is_better'] else 'Lower is better'}"
        )
        if bench_info.get("official_url"):
            st.caption(f"[Official site]({bench_info['official_url']})")

    st.divider()

    # Filters
    col1, col2, col3 = st.columns(3)

    providers = get_unique_providers()

    with col1:
        selected_providers = st.multiselect(
            "Provider",
            options=providers,
            default=[],
            placeholder="All providers",
        )

    with col2:
        date_range = st.date_input(
            "Date range",
            value=(date(2023, 1, 1), date.today()),
        )

    with col3:
        trust_filter = st.multiselect(
            "Trust tier",
            options=["A", "B", "C"],
            default=["A", "B", "C"],
        )

    # Get results
    results = get_results_for_benchmark(
        selected_benchmark,
        min_date=date_range[0] if len(date_range) == 2 else None,
        max_date=date_range[1] if len(date_range) == 2 else None,
        providers=selected_providers if selected_providers else None,
        trust_tiers=trust_filter if trust_filter else None,
    )

    if results.is_empty():
        st.info("No results found for selected filters.")
        return

    results = results.with_columns([
        pl.coalesce(pl.col("evaluation_date"), pl.col("model_release_date")).alias("effective_date")
    ])

    st.caption(f"{len(results)} results")

    # Chart - scatter plot of all results
    st.markdown("### Results Over Time")

    fig = go.Figure()

    colors = ['#4C5C78', '#B8860B', '#6B8E23', '#CD5C5C', '#5F9EA0', '#9370DB', '#D2691E', '#708090']

    for i, provider in enumerate(results["provider"].unique().to_list()):
        provider_data = results.filter(pl.col("provider") == provider).sort("effective_date")

        # Get reasoning effort if available
        reasoning = provider_data["metadata"].to_list() if "metadata" in provider_data.columns else [{}] * len(provider_data)

        fig.add_trace(go.Scatter(
            x=provider_data["effective_date"].to_list(),
            y=provider_data["score"].to_list(),
            mode='markers',
            name=provider,
            marker=dict(size=10, color=colors[i % len(colors)], opacity=0.8),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Score: %{y:.2f}<br>"
                "Provider: " + provider + "<br>"
                "Tier: %{customdata[1]}<extra></extra>"
            ),
            customdata=list(zip(
                provider_data["model_name"].to_list(),
                provider_data["trust_tier"].to_list(),
            )),
        ))

    fig.update_layout(
        xaxis_title="",
        yaxis_title=f"Score ({bench_info['unit']})",
        hovermode="closest",
        height=400,
        margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11),
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(gridcolor='#F0F0F0', showline=True, linecolor='#E8E8E8'),
        yaxis=dict(gridcolor='#F0F0F0', showline=True, linecolor='#E8E8E8'),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Results table
    st.markdown("### All Results")

    display_cols = ["effective_date", "model_name", "provider", "score", "score_stderr", "trust_tier", "source_title"]
    available_cols = [c for c in display_cols if c in results.columns]

    display_df = results.select(available_cols).sort("score", descending=True).to_pandas()

    # Rename columns
    col_names = {
        "effective_date": "Date",
        "model_name": "Model",
        "provider": "Provider",
        "score": "Score",
        "score_stderr": "Stderr",
        "trust_tier": "Tier",
        "source_title": "Source",
    }
    display_df = display_df.rename(columns=col_names)

    # Format score with stderr
    if "Stderr" in display_df.columns:
        display_df["Score"] = display_df.apply(
            lambda r: f"{r['Score']:.2f}" + (f" ± {r['Stderr']:.2f}" if r['Stderr'] else ""),
            axis=1
        )
        display_df = display_df.drop(columns=["Stderr"])

    st.dataframe(display_df, hide_index=True, use_container_width=True)

    st.download_button(
        "Export CSV",
        results.to_pandas().to_csv(index=False),
        f"{selected_benchmark}_results.csv",
        "text/csv",
    )


def render_model_mode():
    """Render model exploration mode."""

    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input(
            "Search models",
            placeholder="Model name or provider...",
        )

    with col2:
        providers = get_unique_providers()
        provider_filter = st.selectbox(
            "Provider",
            options=["All"] + providers,
        )

    # Get models
    if search_query:
        models = search_models(search_query)
    elif provider_filter != "All":
        models = get_all_models(provider=provider_filter)
    else:
        models = get_all_models()

    if models.is_empty():
        st.info("No models found.")
        return

    # Model selector
    model_options = {
        row["model_id"]: f"{row['name']} ({row['provider']})"
        for row in models.head(100).iter_rows(named=True)
    }

    selected_model = st.selectbox(
        "Select Model",
        options=list(model_options.keys()),
        format_func=lambda x: model_options.get(x, x),
    )

    if not selected_model:
        return

    model_info = models.filter(pl.col("model_id") == selected_model)
    if model_info.is_empty():
        return

    model = model_info.row(0, named=True)

    st.divider()

    # Model header
    st.markdown(f"### {model['name']}")

    cols = st.columns(4)
    cols[0].metric("Provider", model["provider"])
    cols[1].metric("Family", model.get("family") or "—")
    cols[2].metric("Released", str(model.get("release_date")) if model.get("release_date") else "—")
    cols[3].metric("Status", "Verified" if model.get("status") == "verified" else "Unverified")

    # Get results
    results = get_results_for_model(selected_model)

    if results.is_empty():
        st.info("No benchmark results found for this model.")
        return

    st.divider()

    # Performance chart
    st.markdown("### Performance Across Benchmarks")

    benchmark_scores = results.group_by("benchmark_name").agg([
        pl.col("score").max().alias("best_score"),
        pl.col("scale_max").first().alias("scale_max"),
    ])

    if not benchmark_scores.is_empty():
        benchmark_scores = benchmark_scores.with_columns([
            (pl.col("best_score") / pl.col("scale_max") * 100).alias("pct_of_max")
        ]).sort("pct_of_max", descending=True)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=benchmark_scores["benchmark_name"].to_list(),
            y=benchmark_scores["pct_of_max"].to_list(),
            marker_color='#4C5C78',
            hovertemplate="<b>%{x}</b><br>%{y:.1f}% of max<extra></extra>",
        ))

        fig.update_layout(
            xaxis_title="",
            yaxis_title="% of max score",
            height=350,
            margin=dict(l=40, r=20, t=20, b=100),
            plot_bgcolor='white',
            xaxis=dict(tickangle=-45, gridcolor='#F0F0F0'),
            yaxis=dict(gridcolor='#F0F0F0', range=[0, 105]),
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Results table
    st.markdown("### Detailed Results")

    display_df = results.select([
        "benchmark_name",
        "category",
        "score",
        "score_stderr",
        "trust_tier",
        "source_title",
    ]).to_pandas()

    display_df["Score"] = display_df.apply(
        lambda r: f"{r['score']:.2f}" + (f" ± {r['score_stderr']:.2f}" if r['score_stderr'] else "")
        if r['score'] is not None else "—",
        axis=1
    )

    display_df = display_df[["benchmark_name", "category", "Score", "trust_tier", "source_title"]]
    display_df.columns = ["Benchmark", "Category", "Score", "Tier", "Source"]

    st.dataframe(display_df, hide_index=True, use_container_width=True)

    st.download_button(
        "Export CSV",
        results.to_pandas().to_csv(index=False),
        f"{selected_model.replace(':', '_')}_results.csv",
        "text/csv",
    )

    st.divider()

    # Model comparison
    st.markdown("### Compare Models")

    compare_models = st.multiselect(
        "Add models to compare",
        options=[m for m in model_options.keys() if m != selected_model],
        format_func=lambda x: model_options.get(x, x),
        max_selections=3,
    )

    if compare_models:
        all_comparison = [results.with_columns(pl.lit(model["name"]).alias("model_display"))]

        for comp_model_id in compare_models:
            comp_results = get_results_for_model(comp_model_id)
            if not comp_results.is_empty():
                comp_info = models.filter(pl.col("model_id") == comp_model_id)
                comp_name = comp_info["name"][0] if len(comp_info) > 0 else comp_model_id
                comp_results = comp_results.with_columns(pl.lit(comp_name).alias("model_display"))
                all_comparison.append(comp_results)

        if len(all_comparison) > 1:
            combined = pl.concat(all_comparison, how="diagonal")

            comparison_df = combined.group_by(["benchmark_name", "model_display"]).agg([
                pl.col("score").max().alias("score")
            ]).to_pandas()

            fig_compare = go.Figure()

            colors = ['#4C5C78', '#B8860B', '#6B8E23', '#CD5C5C']
            for i, model_name in enumerate(comparison_df["model_display"].unique()):
                model_data = comparison_df[comparison_df["model_display"] == model_name]
                fig_compare.add_trace(go.Bar(
                    name=model_name,
                    x=model_data["benchmark_name"],
                    y=model_data["score"],
                    marker_color=colors[i % len(colors)],
                ))

            fig_compare.update_layout(
                barmode='group',
                xaxis_title="",
                yaxis_title="Score",
                height=350,
                margin=dict(l=40, r=20, t=20, b=100),
                plot_bgcolor='white',
                xaxis=dict(tickangle=-45, gridcolor='#F0F0F0'),
                yaxis=dict(gridcolor='#F0F0F0'),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                ),
            )

            st.plotly_chart(fig_compare, use_container_width=True)
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/dashboard/pages/explorer.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/dashboard/pages/explorer.py
git commit -m "feat: add unified explorer page with benchmark/model modes"
```

---

### Task 1.5: Create Admin Page with Data Refresh

**Files:**
- Create: `src/dashboard/pages/admin.py`
- Delete later: `src/dashboard/pages/data_quality.py`

**Step 1: Create admin.py**

Create `src/dashboard/pages/admin.py`:
```python
"""Admin page - data management, refresh, and quality monitoring."""

import streamlit as st
import plotly.graph_objects as go
import polars as pl
from pathlib import Path
import json
import subprocess
import sys
from datetime import datetime

from src.db.queries import (
    get_all_benchmarks,
    get_all_sources,
    get_data_quality_summary,
    get_unique_providers,
)
from src.db.connection import get_last_update, get_connection

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def render_admin():
    """Render the admin page."""

    st.markdown("## Data Administration")

    # Data refresh section
    st.markdown("### Refresh Data")

    with st.container():
        col1, col2 = st.columns([2, 3])

        with col1:
            if st.button("▶ Refresh All Benchmarks", type="primary", use_container_width=True):
                run_data_refresh()

        with col2:
            last_update = get_last_update()
            if last_update:
                st.success(f"Last refresh: {last_update.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            else:
                st.warning("No successful refresh recorded")

    st.divider()

    # Quality summary
    st.markdown("### Data Quality Overview")

    quality = get_data_quality_summary()

    cols = st.columns(5)
    cols[0].metric("Total Results", f"{quality['total_results']:,}")
    cols[1].metric("Models", f"{quality['total_models']:,}")
    cols[2].metric("Benchmarks", quality['total_benchmarks'])
    cols[3].metric("Missing Scores", f"{quality['missing_scores']:,}")
    cols[4].metric("Coverage", f"{100 - quality['missing_score_pct']:.0f}%")

    st.divider()

    # Trust tier distribution
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Trust Tier Distribution")

        st.markdown("""
        **Tier A** — Official sources (benchmark authors, leaderboards)
        **Tier B** — Semi-official (model provider, Epoch AI)
        **Tier C** — Third-party (community runs, blogs)
        """)

        trust_dist = quality["trust_distribution"]
        if not trust_dist.is_empty():
            for row in trust_dist.iter_rows(named=True):
                tier = row["trust_tier"]
                count = row["count"]
                pct = count / quality["total_results"] * 100 if quality["total_results"] > 0 else 0
                st.caption(f"Tier {tier}: {count:,} ({pct:.1f}%)")

    with col2:
        if not trust_dist.is_empty():
            fig = go.Figure(data=[go.Pie(
                labels=trust_dist["trust_tier"].to_list(),
                values=trust_dist["count"].to_list(),
                marker=dict(colors=['#4C5C78', '#B8860B', '#888888']),
                hole=0.4,
                textinfo='label+percent',
            )])
            fig.update_layout(
                height=250,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Coverage matrix
    st.markdown("### Coverage Matrix")

    benchmarks = get_all_benchmarks()
    providers = get_unique_providers()

    if not benchmarks.is_empty() and providers:
        with get_connection(read_only=True) as conn:
            coverage_data = conn.execute("""
                SELECT
                    b.name as benchmark,
                    m.provider,
                    COUNT(CASE WHEN r.score IS NOT NULL THEN 1 END) as valid
                FROM benchmarks b
                CROSS JOIN (SELECT DISTINCT provider FROM models) m
                LEFT JOIN results r ON r.benchmark_id = b.benchmark_id
                LEFT JOIN models mo ON r.model_id = mo.model_id AND mo.provider = m.provider
                GROUP BY b.name, m.provider
            """).pl()

        if not coverage_data.is_empty():
            heatmap_data = coverage_data.pivot(
                on="provider",
                index="benchmark",
                values="valid",
                aggregate_function="sum",
            ).fill_null(0)

            benchmarks_list = heatmap_data["benchmark"].to_list()
            providers_list = [c for c in heatmap_data.columns if c != "benchmark"]
            matrix = heatmap_data.select(providers_list).to_numpy()

            fig = go.Figure(data=go.Heatmap(
                z=matrix,
                x=providers_list,
                y=benchmarks_list,
                colorscale=[[0, '#F5F5F5'], [1, '#4C5C78']],
                hovertemplate="Benchmark: %{y}<br>Provider: %{x}<br>Results: %{z}<extra></extra>",
            ))

            fig.update_layout(
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(tickangle=-45),
            )

            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Data sources
    st.markdown("### Data Sources")

    sources = get_all_sources()

    if not sources.is_empty():
        display_sources = sources.select([
            "source_title",
            "source_type",
            "result_count",
            "retrieved_at",
        ]).sort("retrieved_at", descending=True).to_pandas()

        display_sources.columns = ["Source", "Type", "Results", "Retrieved"]

        st.dataframe(display_sources, hide_index=True, use_container_width=True)
    else:
        st.info("No sources recorded.")

    st.divider()

    # Changelog
    st.markdown("### Recent Changes")

    changelog_path = PROJECT_ROOT / "data" / "changelog.jsonl"

    if changelog_path.exists():
        try:
            with open(changelog_path, "r") as f:
                lines = f.readlines()[-20:]

            if lines:
                changelog_entries = []
                for line in reversed(lines):
                    try:
                        entry = json.loads(line.strip())
                        reason = entry.get("reason", "")
                        changelog_entries.append({
                            "Timestamp": entry.get("timestamp", "")[:19],
                            "Action": entry.get("action", ""),
                            "Table": entry.get("table", ""),
                            "Record": entry.get("record_id", "")[:16] + "..." if len(entry.get("record_id", "")) > 16 else entry.get("record_id", ""),
                            "Reason": (reason[:40] + "...") if reason and len(reason) > 40 else reason,
                        })
                    except json.JSONDecodeError:
                        continue

                if changelog_entries:
                    st.dataframe(changelog_entries, hide_index=True, use_container_width=True)
                else:
                    st.info("No changelog entries found.")
            else:
                st.info("Changelog is empty.")
        except Exception:
            st.info("Could not read changelog.")
    else:
        st.info("No changelog file found.")

    st.divider()

    # Export section
    st.markdown("### Export Data")

    col1, col2 = st.columns(2)

    with col1:
        # Export all results as CSV
        with get_connection(read_only=True) as conn:
            all_results = conn.execute("""
                SELECT
                    r.*,
                    m.name as model_name,
                    m.provider,
                    b.name as benchmark_name,
                    b.category,
                    s.source_title,
                    s.source_url
                FROM results r
                JOIN models m ON r.model_id = m.model_id
                JOIN benchmarks b ON r.benchmark_id = b.benchmark_id
                JOIN sources s ON r.source_id = s.source_id
            """).pl()

        if not all_results.is_empty():
            st.download_button(
                "📥 Export All Data (CSV)",
                all_results.to_pandas().to_csv(index=False),
                f"ai_benchmark_data_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True,
            )

    with col2:
        # Export database file
        db_path = PROJECT_ROOT / "data" / "benchmark.duckdb"
        if db_path.exists():
            with open(db_path, "rb") as f:
                st.download_button(
                    "📥 Export Database (DuckDB)",
                    f.read(),
                    f"benchmark_{datetime.now().strftime('%Y%m%d')}.duckdb",
                    "application/octet-stream",
                    use_container_width=True,
                )


def run_data_refresh():
    """Run the data refresh pipeline with live progress."""

    st.markdown("---")
    st.markdown("#### Refresh Progress")

    progress_container = st.empty()
    log_container = st.empty()

    # Get list of ingestors
    from src.ingestors import INGESTORS

    total = len(INGESTORS)
    completed = 0
    results_log = []

    for benchmark_id, ingestor_cls in INGESTORS.items():
        # Update progress
        progress_container.progress(completed / total, text=f"Processing {benchmark_id}...")

        try:
            ingestor = ingestor_cls()
            result = ingestor.run(dry_run=False)

            if result["success"]:
                status = "✓"
                msg = f"{result['inserted']} results"
            else:
                status = "✗"
                msg = result["errors"][0] if result["errors"] else "Failed"

            results_log.append(f"{status} {benchmark_id}: {msg}")

        except Exception as e:
            results_log.append(f"✗ {benchmark_id}: {str(e)[:50]}")

        completed += 1

        # Update log display
        log_container.code("\n".join(results_log))

    progress_container.progress(1.0, text="Complete!")

    # Update last update timestamp
    from src.db.connection import set_last_update
    set_last_update(datetime.utcnow())

    st.success("Data refresh complete! Reload the page to see updated data.")
    st.button("🔄 Reload Page", on_click=lambda: st.rerun())
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/dashboard/pages/admin.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/dashboard/pages/admin.py
git commit -m "feat: add admin page with data refresh and quality monitoring"
```

---

### Task 1.6: Update Projections Page

**Files:**
- Modify: `src/dashboard/pages/projections.py` (complete rewrite)

**Step 1: Rewrite projections.py with enhanced features**

Replace `src/dashboard/pages/projections.py`:
```python
"""Projections page - mathematical forecasting laboratory."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta
import polars as pl
import numpy as np

from src.db.queries import get_all_benchmarks, get_frontier_results
from src.projections.linear import linear_projection
from src.projections.saturation import saturation_projection


def render_projections():
    """Render the projections page."""

    st.markdown("## Projections")

    st.markdown("""
    <div style="background: #FFFEF5; border-left: 3px solid #B8860B; padding: 0.75rem 1rem; margin: 1rem 0; font-size: 0.9rem; color: #665C00;">
    These projections are mathematical extrapolations assuming stable benchmark definitions.
    They are not forecasts of real-world AI capability. Past trends may not continue.
    </div>
    """, unsafe_allow_html=True)

    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found.")
        return

    st.divider()

    # Configuration columns
    col1, col2, col3 = st.columns(3)

    with col1:
        benchmark_options = {
            row["benchmark_id"]: row["name"]
            for row in benchmarks.iter_rows(named=True)
        }
        selected_benchmark = st.selectbox(
            "Benchmark",
            options=list(benchmark_options.keys()),
            format_func=lambda x: benchmark_options.get(x, x),
        )

    with col2:
        projection_method = st.selectbox(
            "Fitting Method",
            options=["linear", "saturation", "ensemble"],
            format_func=lambda x: {
                "linear": "Linear Extrapolation",
                "saturation": "Logistic (Saturation)",
                "ensemble": "Ensemble (Compare All)",
            }.get(x),
        )

    with col3:
        forecast_months = st.slider("Forecast Horizon (months)", 6, 36, 18)

    col1, col2, col3 = st.columns(3)

    with col1:
        window_months = st.slider("Fitting Window (months)", 6, 36, 18)

    with col2:
        show_ci = st.multiselect(
            "Confidence Intervals",
            ["80%", "95%"],
            default=["80%", "95%"],
        )

    with col3:
        show_residuals = st.checkbox("Show Residuals", value=False)

    # Get benchmark info
    bench_meta = benchmarks.filter(pl.col("benchmark_id") == selected_benchmark)
    if bench_meta.is_empty():
        st.error("Benchmark not found")
        return

    bench_info = bench_meta.row(0, named=True)
    ceiling = bench_info["scale_max"]

    # Get frontier data
    frontier = get_frontier_results(selected_benchmark, min_date=date(2023, 1, 1))

    if frontier.is_empty() or len(frontier) < 5:
        st.warning(f"Insufficient data. Need at least 5 data points, found {len(frontier)}.")
        return

    frontier = frontier.with_columns([
        pl.coalesce(pl.col("evaluation_date"), pl.col("model_release_date")).alias("effective_date")
    ])

    st.divider()

    # Run projections
    projections = {}

    if projection_method == "ensemble" or projection_method == "linear":
        projections["linear"] = linear_projection(
            frontier,
            window_months=window_months,
            forecast_months=forecast_months
        )

    if projection_method == "ensemble" or projection_method == "saturation":
        projections["saturation"] = saturation_projection(
            frontier,
            ceiling=ceiling,
            window_months=window_months,
            forecast_months=forecast_months
        )

    # Filter out failed projections
    projections = {k: v for k, v in projections.items() if v is not None}

    if not projections:
        st.error("All projection methods failed. Try different parameters or more data.")
        return

    # Select primary projection for display
    if projection_method == "ensemble":
        # Use the one with best R²
        primary_method = max(projections.keys(), key=lambda k: projections[k].r_squared or 0)
    else:
        primary_method = projection_method

    projection = projections.get(primary_method)

    if projection is None:
        st.error(f"{primary_method} projection failed. Try different parameters.")
        return

    # Main chart
    st.markdown(f"### {bench_info['name']} Projection")

    fig = go.Figure()

    # Historical data
    fig.add_trace(go.Scatter(
        x=frontier["effective_date"].to_list(),
        y=frontier["score"].to_list(),
        mode='markers+lines',
        name='Historical',
        marker=dict(size=8, color='#4C5C78'),
        line=dict(width=2, color='#4C5C78'),
        hovertemplate="<b>%{customdata}</b><br>Score: %{y:.1f}<extra></extra>",
        customdata=frontier["model_name"].to_list(),
    ))

    # Primary projection line
    fig.add_trace(go.Scatter(
        x=projection.forecast_dates,
        y=projection.forecast_values,
        mode='lines',
        name=f'Projection ({primary_method.title()})',
        line=dict(width=2, color='#B8860B', dash='dash'),
    ))

    # Confidence intervals
    if "95%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_95_high + projection.ci_95_low[::-1],
            fill='toself',
            fillcolor='rgba(184, 134, 11, 0.1)',
            line=dict(color='rgba(255,255,255,0)'),
            name='95% CI',
            hoverinfo='skip',
        ))

    if "80%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_80_high + projection.ci_80_low[::-1],
            fill='toself',
            fillcolor='rgba(184, 134, 11, 0.15)',
            line=dict(color='rgba(255,255,255,0)'),
            name='80% CI',
            hoverinfo='skip',
        ))

    # Ensemble: show other methods as lighter lines
    if projection_method == "ensemble":
        other_colors = {"linear": "#6B8E9F", "saturation": "#8B7355"}
        for method, proj in projections.items():
            if method != primary_method:
                fig.add_trace(go.Scatter(
                    x=proj.forecast_dates,
                    y=proj.forecast_values,
                    mode='lines',
                    name=f'{method.title()}',
                    line=dict(width=1.5, color=other_colors.get(method, '#888'), dash='dot'),
                    opacity=0.7,
                ))

    # Ceiling line for saturation model
    if primary_method == "saturation" or projection_method == "ensemble":
        fig.add_hline(
            y=ceiling,
            line_dash="dot",
            line_color="#999",
            annotation_text=f"Max: {ceiling}",
            annotation_position="right",
        )

    fig.update_layout(
        xaxis_title="",
        yaxis_title=f"Score ({bench_info['unit']})",
        height=450,
        margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11),
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(gridcolor='#F0F0F0', showline=True, linecolor='#E8E8E8'),
        yaxis=dict(gridcolor='#F0F0F0', showline=True, linecolor='#E8E8E8'),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Fit diagnostics
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Method", primary_method.title())
    col2.metric("R² (fit quality)", f"{projection.r_squared:.3f}" if projection.r_squared else "—")
    col3.metric("Fitting Window", f"{projection.fit_window_start} → {projection.fit_window_end}")
    col4.metric(
        f"Projected ({projection.forecast_dates[-1]})",
        f"{projection.forecast_values[-1]:.1f}"
    )

    # Ensemble comparison table
    if projection_method == "ensemble" and len(projections) > 1:
        st.divider()
        st.markdown("### Model Comparison")

        comparison_data = []
        for method, proj in projections.items():
            comparison_data.append({
                "Method": method.title(),
                "R²": f"{proj.r_squared:.3f}" if proj.r_squared else "—",
                "12-mo Forecast": f"{proj.forecast_values[min(11, len(proj.forecast_values)-1)]:.1f}",
                "Final Forecast": f"{proj.forecast_values[-1]:.1f}",
            })

        st.dataframe(comparison_data, hide_index=True, use_container_width=True)

    st.divider()

    # Time-to-threshold calculator
    st.markdown("### Time-to-Threshold Calculator")

    col1, col2 = st.columns(2)

    with col1:
        threshold = st.slider(
            f"Target score for {bench_info['name']}",
            min_value=int(bench_info["scale_min"]),
            max_value=int(bench_info["scale_max"]),
            value=min(90, int(ceiling * 0.9)),
        )

    with col2:
        # Find when projection crosses threshold
        forecast_values = np.array(projection.forecast_values)
        forecast_dates = projection.forecast_dates

        crossing_idx = np.where(forecast_values >= threshold)[0]

        if len(crossing_idx) > 0:
            crossing_date = forecast_dates[crossing_idx[0]]

            # Find CI crossings
            ci_80_low_cross = np.where(np.array(projection.ci_80_low) >= threshold)[0]
            ci_80_high_cross = np.where(np.array(projection.ci_80_high) >= threshold)[0]

            late_date = forecast_dates[ci_80_low_cross[0]] if len(ci_80_low_cross) > 0 else "Beyond forecast"
            early_date = forecast_dates[ci_80_high_cross[0]] if len(ci_80_high_cross) > 0 else crossing_date

            st.metric(
                f"Projected to reach {threshold}",
                str(crossing_date),
                delta=f"80% CI: {early_date} – {late_date}" if isinstance(late_date, date) else None,
            )
        else:
            current_max = frontier["score"].max()
            if current_max >= threshold:
                st.success(f"Already achieved! Current best: {current_max:.1f}")
            else:
                st.info(f"Not projected to reach {threshold} within forecast horizon.")

    st.divider()

    # Forecast table
    st.markdown("### Forecast Values")

    forecast_df = pl.DataFrame({
        "Date": projection.forecast_dates,
        "Projected": projection.forecast_values,
        "80% Low": projection.ci_80_low,
        "80% High": projection.ci_80_high,
        "95% Low": projection.ci_95_low,
        "95% High": projection.ci_95_high,
    })

    st.dataframe(forecast_df.to_pandas().round(2), hide_index=True, use_container_width=True)

    st.download_button(
        "Export Forecast (CSV)",
        forecast_df.to_pandas().to_csv(index=False),
        f"{selected_benchmark}_forecast.csv",
        "text/csv",
    )
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/dashboard/pages/projections.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/dashboard/pages/projections.py
git commit -m "feat: enhance projections page with ensemble mode and time-to-threshold"
```

---

### Task 1.7: Update Pages __init__ and Clean Up Old Files

**Files:**
- Modify: `src/dashboard/pages/__init__.py`
- Delete: `src/dashboard/pages/overview.py`
- Delete: `src/dashboard/pages/benchmark_explorer.py`
- Delete: `src/dashboard/pages/model_explorer.py`
- Delete: `src/dashboard/pages/data_quality.py`

**Step 1: Update pages __init__.py**

Replace `src/dashboard/pages/__init__.py`:
```python
"""Dashboard pages."""

from .progress import render_progress
from .explorer import render_explorer
from .projections import render_projections
from .admin import render_admin

__all__ = [
    "render_progress",
    "render_explorer",
    "render_projections",
    "render_admin",
]
```

**Step 2: Delete old page files**

Run:
```bash
rm src/dashboard/pages/overview.py
rm src/dashboard/pages/benchmark_explorer.py
rm src/dashboard/pages/model_explorer.py
rm src/dashboard/pages/data_quality.py
```

**Step 3: Verify app loads**

Run: `cd /Users/kylemoskowitz/Documents/Programming/ai-benchmark-dashboard && python -c "from src.dashboard.pages import *; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: consolidate pages to 4-page structure, remove old files"
```

---

## Phase 2: New Benchmark Ingestors

### Task 2.1: Add ARC-AGI Ingestors

**Files:**
- Create: `src/ingestors/arc_agi.py`
- Modify: `src/ingestors/__init__.py`
- Modify: `data/benchmarks.yml`

**Step 1: Create ARC-AGI ingestor**

Create `src/ingestors/arc_agi.py`:
```python
"""ARC-AGI benchmark ingestors (versions 1 and 2)."""

from datetime import datetime, date
from pathlib import Path
import httpx
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class ARCAGIBaseIngestor(BaseIngestor):
    """Base ingestor for ARC-AGI benchmarks."""

    # Override in subclasses
    LEADERBOARD_URL = ""
    VERSION = ""

    def fetch_raw(self) -> Path:
        """Fetch ARC-AGI leaderboard data."""
        # Try local snapshot first
        snapshot_name = f"arc_agi_{self.VERSION}.csv"
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / snapshot_name

        if snapshot_path.exists():
            return snapshot_path

        # Otherwise fetch from web
        # Note: ARC Prize doesn't have a public API, so we rely on snapshots
        raise FileNotFoundError(
            f"ARC-AGI {self.VERSION} snapshot not found at {snapshot_path}. "
            "Please download manually from arcprize.org."
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse ARC-AGI CSV into Result objects."""
        df = pl.read_csv(raw_path)

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title=f"ARC Prize {self.VERSION} Leaderboard",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        # Expected columns: model, provider, score, date, reasoning_effort (optional)
        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("model") or row.get("Model") or ""
                if not model_name:
                    continue

                provider = row.get("provider") or row.get("Provider") or self._infer_provider(model_name)
                score = self._parse_float(row.get("score") or row.get("Score"))
                eval_date = self.parse_date(row.get("date") or row.get("Date"))
                reasoning_effort = row.get("reasoning_effort") or row.get("Reasoning Effort")

                # Include reasoning effort in model name if present
                display_name = model_name
                if reasoning_effort:
                    display_name = f"{model_name} ({reasoning_effort})"

                model_id = self.normalize_model_id(display_name, provider)

                model = Model(
                    model_id=model_id,
                    name=display_name,
                    provider=provider,
                    family=self._infer_family(model_name),
                    release_date=eval_date,
                    status=ModelStatus.VERIFIED,
                    metadata={"reasoning_effort": reasoning_effort} if reasoning_effort else {},
                )
                self.register_model(model)

                result = Result(
                    result_id=self.generate_result_id(model_id, eval_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    evaluation_date=eval_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,  # Official leaderboard
                    evaluation_notes=f"ARC Prize {self.VERSION} official result",
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")

        return results

    def _infer_family(self, model_name: str) -> str | None:
        name_lower = model_name.lower()
        families = {
            "o3": ["o3"], "o4": ["o4"], "o1": ["o1"],
            "gpt-4": ["gpt-4"], "gpt-5": ["gpt-5"],
            "claude-4": ["claude-4", "opus-4", "sonnet-4"],
            "claude-3.5": ["claude-3-5", "claude-3.5"],
            "gemini-2": ["gemini-2"], "gemini-3": ["gemini-3"],
        }
        for family, patterns in families.items():
            for p in patterns:
                if p in name_lower:
                    return family
        return None

    def _parse_float(self, value) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


class ARCAGI1Ingestor(ARCAGIBaseIngestor):
    """Ingestor for ARC-AGI 1 (original)."""

    BENCHMARK_ID = "arc_agi_1"
    VERSION = "1"
    LEADERBOARD_URL = "https://arcprize.org/leaderboard"

    BENCHMARK_META = Benchmark(
        benchmark_id="arc_agi_1",
        name="ARC-AGI 1",
        category="reasoning",
        description="Original Abstraction and Reasoning Corpus evaluating fluid intelligence and novel problem solving.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://arcprize.org/",
        paper_url="https://arxiv.org/abs/1911.01547",
    )


class ARCAGI2Ingestor(ARCAGIBaseIngestor):
    """Ingestor for ARC-AGI 2."""

    BENCHMARK_ID = "arc_agi_2"
    VERSION = "2"
    LEADERBOARD_URL = "https://arcprize.org/arc-agi-2"

    BENCHMARK_META = Benchmark(
        benchmark_id="arc_agi_2",
        name="ARC-AGI 2",
        category="reasoning",
        description="Updated ARC-AGI with harder tasks and improved evaluation methodology.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://arcprize.org/arc-agi-2",
    )
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/ingestors/arc_agi.py`
Expected: No output

**Step 3: Update ingestors __init__.py**

Add to `src/ingestors/__init__.py`:
```python
from .arc_agi import ARCAGI1Ingestor, ARCAGI2Ingestor

# In INGESTORS dict:
"arc_agi_1": ARCAGI1Ingestor,
"arc_agi_2": ARCAGI2Ingestor,
```

**Step 4: Update benchmarks.yml**

Add to `data/benchmarks.yml`:
```yaml
  arc_agi_1:
    name: "ARC-AGI 1"
    category: "reasoning"
    description: "Original ARC evaluating fluid intelligence."
    unit: "percent"
    scale_min: 0
    scale_max: 100
    higher_is_better: true
    official_url: "https://arcprize.org/"

  arc_agi_2:
    name: "ARC-AGI 2"
    category: "reasoning"
    description: "Updated ARC with harder tasks."
    unit: "percent"
    scale_min: 0
    scale_max: 100
    higher_is_better: true
    official_url: "https://arcprize.org/arc-agi-2"
```

**Step 5: Commit**

```bash
git add src/ingestors/arc_agi.py src/ingestors/__init__.py data/benchmarks.yml
git commit -m "feat: add ARC-AGI 1 and 2 ingestors"
```

---

### Task 2.2: Add MMMU Ingestor

**Files:**
- Create: `src/ingestors/mmmu.py`
- Modify: `src/ingestors/__init__.py`
- Modify: `data/benchmarks.yml`

**Step 1: Create MMMU ingestor**

Create `src/ingestors/mmmu.py`:
```python
"""MMMU benchmark ingestor - Massive Multi-discipline Multimodal Understanding."""

from datetime import datetime
from pathlib import Path
import polars as pl

from .base import BaseIngestor
from src.models.schemas import (
    Result, Source, Model, Benchmark,
    TrustTier, SourceType, ParseMethod, ModelStatus
)


class MMMUIngestor(BaseIngestor):
    """Ingestor for MMMU benchmark."""

    BENCHMARK_ID = "mmmu"
    LEADERBOARD_URL = "https://mmmu-benchmark.github.io/"

    BENCHMARK_META = Benchmark(
        benchmark_id="mmmu",
        name="MMMU",
        category="multimodal",
        description="Massive Multi-discipline Multimodal Understanding - evaluates multimodal models on college-level tasks.",
        unit="percent",
        scale_min=0.0,
        scale_max=100.0,
        higher_is_better=True,
        official_url="https://mmmu-benchmark.github.io/",
        paper_url="https://arxiv.org/abs/2311.16502",
    )

    def fetch_raw(self) -> Path:
        """Fetch MMMU data from snapshot."""
        snapshot_path = Path(__file__).parent.parent.parent / "data" / "snapshots" / "mmmu.csv"

        if snapshot_path.exists():
            return snapshot_path

        raise FileNotFoundError(
            f"MMMU snapshot not found at {snapshot_path}. "
            "Please download from mmmu-benchmark.github.io."
        )

    def parse(self, raw_path: Path) -> list[Result]:
        """Parse MMMU CSV."""
        df = pl.read_csv(raw_path)

        source = Source(
            source_id=self.generate_source_id(self.LEADERBOARD_URL),
            source_type=SourceType.OFFICIAL_LEADERBOARD,
            source_title="MMMU Official Leaderboard",
            source_url=self.LEADERBOARD_URL,
            retrieved_at=datetime.utcnow(),
            parse_method=ParseMethod.CSV_DOWNLOAD,
            raw_snapshot_path=str(raw_path),
        )
        self.register_source(source)

        results = []

        for row in df.iter_rows(named=True):
            try:
                model_name = row.get("model") or row.get("Model") or ""
                if not model_name:
                    continue

                provider = row.get("provider") or self._infer_provider(model_name)
                score = self._parse_float(row.get("score") or row.get("val_score") or row.get("Score"))
                eval_date = self.parse_date(row.get("date"))

                model_id = self.normalize_model_id(model_name, provider)

                model = Model(
                    model_id=model_id,
                    name=model_name,
                    provider=provider,
                    release_date=eval_date,
                    status=ModelStatus.VERIFIED,
                )
                self.register_model(model)

                result = Result(
                    result_id=self.generate_result_id(model_id, eval_date),
                    model_id=model_id,
                    benchmark_id=self.BENCHMARK_ID,
                    score=score,
                    evaluation_date=eval_date,
                    source_id=source.source_id,
                    trust_tier=TrustTier.A,
                )
                results.append(result)

            except Exception as e:
                self.log_warning(f"Failed to parse row: {e}")

        return results

    def _parse_float(self, value) -> float | None:
        if value is None or value == "":
            return None
        try:
            v = float(value)
            return v * 100 if v <= 1 else v
        except (ValueError, TypeError):
            return None
```

**Step 2: Verify and commit**

Run: `python -m py_compile src/ingestors/mmmu.py`

Update `src/ingestors/__init__.py` to add:
```python
from .mmmu import MMMUIngestor
# In INGESTORS: "mmmu": MMMUIngestor,
```

```bash
git add src/ingestors/mmmu.py src/ingestors/__init__.py data/benchmarks.yml
git commit -m "feat: add MMMU multimodal benchmark ingestor"
```

---

### Task 2.3: Add Remaining Ingestors (ZeroBench, Humanities Last Exam, Remote Labor Index, Epoch Capabilities Index)

**Files:**
- Create: `src/ingestors/zerobench.py`
- Create: `src/ingestors/humanities_last_exam.py`
- Create: `src/ingestors/remote_labor_index.py`
- Create: `src/ingestors/epoch_capabilities_index.py`
- Modify: `src/ingestors/__init__.py`
- Modify: `data/benchmarks.yml`

Each ingestor follows the same pattern as above. Create skeleton ingestors that can load from CSV snapshots.

**Step 1: Create zerobench.py, humanities_last_exam.py, remote_labor_index.py, epoch_capabilities_index.py**

(Follow same pattern as mmmu.py with appropriate BENCHMARK_ID, BENCHMARK_META, and column mappings)

**Step 2: Update __init__.py with all new ingestors**

**Step 3: Update benchmarks.yml with all new benchmark definitions**

**Step 4: Commit**

```bash
git add src/ingestors/*.py src/ingestors/__init__.py data/benchmarks.yml
git commit -m "feat: add remaining benchmark ingestors (ZeroBench, HLE, RLI, Epoch)"
```

---

## Phase 3: Data and Testing

### Task 3.1: Create Sample Data Snapshots

**Files:**
- Create: `data/snapshots/arc_agi_1.csv`
- Create: `data/snapshots/arc_agi_2.csv`
- Create: `data/snapshots/mmmu.csv`
- Create: `data/snapshots/zerobench.csv`
- Create: `data/snapshots/humanities_last_exam.csv`
- Create: `data/snapshots/remote_labor_index.csv`
- Create: `data/snapshots/epoch_capabilities_index.csv`

Create CSV files with headers and sample data for each benchmark.

Example `data/snapshots/arc_agi_1.csv`:
```csv
model,provider,score,date,reasoning_effort
o3,OpenAI,87.5,2024-12-20,high
o3,OpenAI,75.7,2024-12-20,medium
Claude Opus 4.5,Anthropic,21.0,2025-01-30,
GPT-4o,OpenAI,5.0,2024-05-13,
Gemini 2.0 Flash,Google,4.0,2024-12-11,
```

**Step 1: Create snapshot files with real data from public sources**

**Step 2: Commit**

```bash
git add data/snapshots/*.csv
git commit -m "data: add benchmark data snapshots"
```

---

### Task 3.2: Reinitialize Database with New Benchmarks

**Step 1: Run database initialization**

```bash
cd /Users/kylemoskowitz/Documents/Programming/ai-benchmark-dashboard
make init-db
```

**Step 2: Run data update**

```bash
make update-data
```

**Step 3: Verify data loaded**

```bash
python -c "from src.db.connection import get_connection; conn = get_connection(); print(conn.execute('SELECT COUNT(*) FROM results').fetchone())"
```

**Step 4: Commit any changes**

```bash
git add data/benchmark.duckdb
git commit -m "data: reinitialize database with new benchmarks"
```

---

### Task 3.3: Test Dashboard Runs

**Step 1: Start dashboard**

```bash
streamlit run src/dashboard/app.py
```

**Step 2: Manually verify each page loads**

- Progress page shows hero metric and chart
- Explorer works in both modes
- Projections shows forecasts
- Admin shows data refresh

**Step 3: Fix any runtime errors**

---

## Phase 4: Final Polish

### Task 4.1: Add Power Law Projection Method

**Files:**
- Create: `src/projections/power_law.py`
- Modify: `src/dashboard/pages/projections.py`

**Step 1: Create power_law.py**

Implement power law fitting for scaling law projections.

**Step 2: Integrate into projections page**

**Step 3: Commit**

```bash
git add src/projections/power_law.py src/dashboard/pages/projections.py
git commit -m "feat: add power law projection method"
```

---

### Task 4.2: Final Cleanup and Documentation

**Files:**
- Modify: `README.md`
- Delete unused files

**Step 1: Update README with new structure**

**Step 2: Remove any unused imports or dead code**

**Step 3: Final commit**

```bash
git add -A
git commit -m "docs: update README for redesigned dashboard"
```

---

## Summary

This plan covers:

1. **Phase 1**: Core UI restructure (7 tasks)
   - New Streamlit theme and CSS
   - 4-page navigation structure
   - Progress, Explorer, Projections, Admin pages
   - Cleanup of old files

2. **Phase 2**: New benchmark ingestors (3 tasks)
   - ARC-AGI 1 & 2
   - MMMU, ZeroBench, Humanities Last Exam
   - Remote Labor Index, Epoch Capabilities Index

3. **Phase 3**: Data and testing (3 tasks)
   - Sample data snapshots
   - Database reinitialization
   - End-to-end testing

4. **Phase 4**: Final polish (2 tasks)
   - Power law projections
   - Documentation updates

Total: ~15 tasks across 4 phases
