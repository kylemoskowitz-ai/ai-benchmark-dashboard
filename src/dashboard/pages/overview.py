"""Overview page - frontier performance across benchmarks."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date
import polars as pl

from src.db.queries import (
    get_all_benchmarks,
    get_frontier_results,
    get_data_quality_summary,
)


def render_overview():
    """Render the overview page."""
    st.title("Overview")

    # Get data
    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found. Run `make update-data` to load data.")
        return

    quality = get_data_quality_summary()

    # Key metrics - simple row
    cols = st.columns(4)
    cols[0].metric("Results", f"{quality['total_results']:,}")
    cols[1].metric("Models", f"{quality['total_models']:,}")
    cols[2].metric("Benchmarks", quality['total_benchmarks'])
    cols[3].metric("Coverage", f"{100 - quality['missing_score_pct']:.0f}%")

    st.divider()

    # Benchmark selector
    benchmark_names = {
        row["benchmark_id"]: row["name"]
        for row in benchmarks.iter_rows(named=True)
    }

    col1, col2, col3 = st.columns([3, 2, 1])

    with col1:
        selected_benchmarks = st.multiselect(
            "Benchmarks",
            options=list(benchmark_names.keys()),
            default=list(benchmark_names.keys())[:5],
            format_func=lambda x: benchmark_names.get(x, x),
        )

    with col2:
        date_range = st.date_input(
            "Date range",
            value=(date(2024, 1, 1), date.today()),
        )

    with col3:
        normalize = st.checkbox("Normalize", value=False)

    if not selected_benchmarks:
        st.info("Select at least one benchmark.")
        return

    # Gather frontier data
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

        bench_meta = benchmarks.filter(pl.col("benchmark_id") == bench_id)
        bench_name = bench_meta["name"][0] if len(bench_meta) > 0 else bench_id
        scale_max = bench_meta["scale_max"][0] if len(bench_meta) > 0 else 100

        frontier = frontier.with_columns([
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
        st.warning("No data found for selected benchmarks.")
        return

    combined = pl.concat(all_frontiers, how="diagonal")

    # Main chart - minimal styling
    st.markdown("### Frontier Progress")

    fig = go.Figure()

    # Muted color palette
    colors = ['#4C78A8', '#F58518', '#54A24B', '#E45756', '#72B7B2', '#B279A2']

    for i, bench_name in enumerate(combined["benchmark_name"].unique().to_list()):
        bench_data = combined.filter(pl.col("benchmark_name") == bench_name).sort("effective_date")

        fig.add_trace(go.Scatter(
            x=bench_data["effective_date"].to_list(),
            y=bench_data["display_score"].to_list(),
            mode='lines+markers',
            name=bench_name,
            line=dict(width=2, color=colors[i % len(colors)]),
            marker=dict(size=6),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Score: %{y:.1f}<br>"
                "Date: %{x}<extra></extra>"
            ),
            customdata=[[m] for m in bench_data["model_name"].to_list()],
        ))

    fig.update_layout(
        xaxis_title="",
        yaxis_title="Score" + (" (%)" if normalize else ""),
        hovermode="closest",
        height=420,
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
        xaxis=dict(gridcolor='#f0f0f0', showline=True, linecolor='#ddd'),
        yaxis=dict(gridcolor='#f0f0f0', showline=True, linecolor='#ddd'),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Export
    st.download_button(
        "Export CSV",
        combined.to_pandas().to_csv(index=False),
        "frontier_data.csv",
        "text/csv",
    )

    st.divider()

    # Recent records - clean table
    st.markdown("### Recent Records")

    recent = combined.sort("effective_date", descending=True).head(10)

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
