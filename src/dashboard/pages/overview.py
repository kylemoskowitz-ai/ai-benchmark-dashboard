"""Overview page - frontier best-over-time across all benchmarks."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import polars as pl

from src.db.queries import (
    get_all_benchmarks,
    get_frontier_results,
    get_data_quality_summary,
)


def render_overview():
    """Render the overview page."""
    st.title("AI Benchmark Progress Overview")
    st.caption("Frontier performance across key benchmarks over time")

    # Get data
    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found. Run `make update-data` to load data.")
        return

    # Key metrics row
    quality = get_data_quality_summary()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Results", f"{quality['total_results']:,}")
    with col2:
        st.metric("Models Tracked", f"{quality['total_models']:,}")
    with col3:
        st.metric("Benchmarks", quality['total_benchmarks'])
    with col4:
        st.metric("Data Coverage", f"{100 - quality['missing_score_pct']:.1f}%")

    st.divider()

    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        selected_benchmarks = st.multiselect(
            "Benchmarks to show",
            options=benchmarks["benchmark_id"].to_list(),
            default=benchmarks["benchmark_id"].to_list()[:5],
            format_func=lambda x: benchmarks.filter(
                pl.col("benchmark_id") == x
            )["name"][0] if len(benchmarks.filter(pl.col("benchmark_id") == x)) > 0 else x,
        )

    with col2:
        date_range = st.date_input(
            "Date range",
            value=(date(2024, 1, 1), date.today()),
            min_value=date(2023, 1, 1),
            max_value=date.today(),
        )

    with col3:
        normalize = st.checkbox("Normalize scores", value=False, help="Scale all benchmarks to 0-100%")

    # Get frontier results for each benchmark
    if not selected_benchmarks:
        st.info("Select at least one benchmark to display.")
        return

    # Prepare data for multi-benchmark frontier chart
    all_frontiers = []

    trust_tiers = ["A", "B"] if st.session_state.get("official_only") else None

    for bench_id in selected_benchmarks:
        frontier = get_frontier_results(
            bench_id,
            min_date=date_range[0] if len(date_range) == 2 else date(2024, 1, 1),
            trust_tiers=trust_tiers,
        )

        if frontier.is_empty():
            continue

        # Get benchmark metadata
        bench_meta = benchmarks.filter(pl.col("benchmark_id") == bench_id)
        bench_name = bench_meta["name"][0] if len(bench_meta) > 0 else bench_id
        scale_max = bench_meta["scale_max"][0] if len(bench_meta) > 0 else 100

        # Add benchmark info
        frontier = frontier.with_columns([
            pl.lit(bench_name).alias("benchmark_name"),
            pl.lit(scale_max).alias("scale_max"),
        ])

        # Normalize if requested
        if normalize and scale_max > 0:
            frontier = frontier.with_columns([
                (pl.col("score") / scale_max * 100).alias("normalized_score")
            ])
        else:
            frontier = frontier.with_columns([
                pl.col("score").alias("normalized_score")
            ])

        all_frontiers.append(frontier)

    if not all_frontiers:
        st.warning("No data found for selected benchmarks and filters.")
        return

    # Combine all frontiers
    combined = pl.concat(all_frontiers, how="diagonal")

    # Create frontier chart
    st.subheader("Frontier Progress Over Time")

    fig = go.Figure()

    for bench_name in combined["benchmark_name"].unique().to_list():
        bench_data = combined.filter(pl.col("benchmark_name") == bench_name)
        bench_data = bench_data.sort("effective_date")

        # Get dates and scores
        dates = bench_data["effective_date"].to_list()
        scores = bench_data["normalized_score"].to_list()
        models = bench_data["model_name"].to_list()
        trust = bench_data["trust_tier"].to_list()

        # Create hover text with provenance
        hover_text = [
            f"<b>{model}</b><br>"
            f"Score: {score:.1f}{'%' if normalize else ''}<br>"
            f"Trust: {t}<br>"
            f"Date: {d}"
            for model, score, t, d in zip(models, scores, trust, dates)
        ]

        fig.add_trace(go.Scatter(
            x=dates,
            y=scores,
            mode='lines+markers',
            name=bench_name,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_text,
            line=dict(width=2),
            marker=dict(size=8),
        ))

    fig.update_layout(
        title="Best Performance Over Time (Frontier)",
        xaxis_title="Date",
        yaxis_title="Score" + (" (Normalized %)" if normalize else ""),
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=500,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Export options
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("📥 Export CSV"):
            csv = combined.to_pandas().to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "frontier_data.csv",
                "text/csv",
            )

    # Recent records section
    st.subheader("Recent Frontier Records")

    recent = combined.sort("effective_date", descending=True).head(10)

    if not recent.is_empty():
        display_df = recent.select([
            "effective_date",
            "model_name",
            "benchmark_name",
            "score",
            "trust_tier",
            "provider",
        ]).to_pandas()

        display_df.columns = ["Date", "Model", "Benchmark", "Score", "Trust", "Provider"]

        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
        )

    # Trust tier distribution
    st.subheader("Data Quality Overview")

    col1, col2 = st.columns(2)

    with col1:
        trust_dist = quality["trust_distribution"]
        if not trust_dist.is_empty():
            fig_trust = px.pie(
                trust_dist.to_pandas(),
                values="count",
                names="trust_tier",
                title="Trust Tier Distribution",
                color="trust_tier",
                color_discrete_map={"A": "#1a7f37", "B": "#9a6700", "C": "#6e7781"},
            )
            st.plotly_chart(fig_trust, use_container_width=True)

    with col2:
        coverage = quality["benchmark_coverage"]
        if not coverage.is_empty():
            fig_coverage = px.bar(
                coverage.to_pandas(),
                x="name",
                y="result_count",
                title="Results per Benchmark",
                color="valid_scores",
                labels={"name": "Benchmark", "result_count": "Results"},
            )
            fig_coverage.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_coverage, use_container_width=True)
