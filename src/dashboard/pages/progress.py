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
    "epoch_capabilities_index": "#4C5C78",
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

    # Get available benchmarks
    available_benchmarks = benchmarks["benchmark_id"].to_list()

    col1, col2 = st.columns([3, 1])
    with col1:
        default_selection = [b for b in BENCHMARK_ORDER[:5] if b in available_benchmarks]
        if not default_selection:
            default_selection = available_benchmarks[:5]

        selected_benchmarks = st.multiselect(
            "Benchmarks",
            options=[b for b in BENCHMARK_ORDER if b in available_benchmarks] or available_benchmarks,
            default=default_selection,
            format_func=lambda x: benchmarks.filter(pl.col("benchmark_id") == x)["name"][0]
                if x in available_benchmarks else x,
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

        if bench_id not in available_benchmarks:
            continue

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

    if cards_data:
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
                            <div class="model">↑ {card["model"][:25]}{"..." if len(str(card["model"])) > 25 else ""}</div>
                            <div class="date">{card["date"]}</div>
                        </div>
                        """, unsafe_allow_html=True)

    st.divider()

    # Recent records table
    st.markdown("### Recent Records")

    recent = combined.sort("effective_date", descending=True).head(15)

    if not recent.is_empty():
        display_cols = ["effective_date", "model_name", "benchmark_name", "score"]
        if "trust_tier" in recent.columns:
            display_cols.append("trust_tier")

        display_df = recent.select([c for c in display_cols if c in recent.columns]).to_pandas()

        col_mapping = {
            "effective_date": "Date",
            "model_name": "Model",
            "benchmark_name": "Benchmark",
            "score": "Score",
            "trust_tier": "Tier"
        }
        display_df = display_df.rename(columns={k: v for k, v in col_mapping.items() if k in display_df.columns})

        if "Score" in display_df.columns:
            display_df["Score"] = display_df["Score"].round(2)

        st.dataframe(display_df, hide_index=True, use_container_width=True)

    # Export
    st.download_button(
        "Export Data (CSV)",
        combined.to_pandas().to_csv(index=False),
        "frontier_progress.csv",
        "text/csv",
    )
