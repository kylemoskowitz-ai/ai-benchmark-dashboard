"""Benchmark Explorer page - deep dive into single benchmark."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import polars as pl

from src.db.queries import (
    get_all_benchmarks,
    get_results_for_benchmark,
    get_unique_providers,
)


def render_benchmark_explorer():
    """Render the benchmark explorer page."""
    st.title("Benchmark Explorer")
    st.caption("Deep dive into individual benchmark results")

    # Get benchmarks
    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found. Run `make update-data` to load data.")
        return

    # Benchmark selector
    col1, col2 = st.columns([3, 1])

    with col1:
        benchmark_options = {
            row["benchmark_id"]: f"{row['name']} ({row['category']})"
            for row in benchmarks.iter_rows(named=True)
        }

        selected_benchmark = st.selectbox(
            "Select Benchmark",
            options=list(benchmark_options.keys()),
            format_func=lambda x: benchmark_options.get(x, x),
        )

    # Get benchmark metadata
    bench_meta = benchmarks.filter(pl.col("benchmark_id") == selected_benchmark)
    if bench_meta.is_empty():
        st.error("Benchmark not found")
        return

    bench_info = bench_meta.row(0, named=True)

    with col2:
        st.metric("Category", bench_info["category"])

    # Benchmark info
    with st.expander("📋 Benchmark Details", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Unit:** {bench_info['unit']}")
            st.write(f"**Scale:** {bench_info['scale_min']} - {bench_info['scale_max']}")
        with col2:
            st.write(f"**Higher is better:** {'Yes' if bench_info['higher_is_better'] else 'No'}")
            if bench_info.get("official_url"):
                st.write(f"**Official URL:** [{bench_info['official_url']}]({bench_info['official_url']})")
        with col3:
            if bench_info.get("notes"):
                st.write(f"**Notes:** {bench_info['notes']}")

    st.divider()

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    providers = get_unique_providers()

    with col1:
        selected_providers = st.multiselect(
            "Filter by Provider",
            options=providers,
            default=[],
            placeholder="All providers",
        )

    with col2:
        date_range = st.date_input(
            "Date Range",
            value=(date(2024, 1, 1), date.today()),
        )

    with col3:
        trust_filter = st.multiselect(
            "Trust Tier",
            options=["A", "B", "C"],
            default=["A", "B", "C"] if not st.session_state.get("official_only") else ["A"],
        )

    with col4:
        show_stderr = st.checkbox("Show error bars", value=True)

    # Get results
    results = get_results_for_benchmark(
        selected_benchmark,
        min_date=date_range[0] if len(date_range) == 2 else None,
        max_date=date_range[1] if len(date_range) == 2 else None,
        providers=selected_providers if selected_providers else None,
        trust_tiers=trust_filter if trust_filter else None,
    )

    if results.is_empty():
        st.warning("No results found for selected filters.")
        return

    # Add effective date column
    results = results.with_columns([
        pl.coalesce(pl.col("evaluation_date"), pl.col("model_release_date")).alias("effective_date")
    ])

    # Main scatter plot
    st.subheader("Results Over Time")

    fig = go.Figure()

    # Group by provider for coloring
    for provider in results["provider"].unique().to_list():
        provider_data = results.filter(pl.col("provider") == provider)
        provider_data = provider_data.sort("effective_date")

        dates = provider_data["effective_date"].to_list()
        scores = provider_data["score"].to_list()
        models = provider_data["model_name"].to_list()
        trust = provider_data["trust_tier"].to_list()
        stderr = provider_data["score_stderr"].to_list()

        # Hover text with provenance
        hover_text = []
        for i, row in enumerate(provider_data.iter_rows(named=True)):
            text = (
                f"<b>{row['model_name']}</b><br>"
                f"Score: {row['score']:.2f}"
            )
            if row.get("score_stderr"):
                text += f" ± {row['score_stderr']:.2f}"
            text += f"<br>Trust: {row['trust_tier']}"
            text += f"<br>Source: {row.get('source_title', 'N/A')}"
            if row.get("evaluation_notes"):
                text += f"<br>Notes: {row['evaluation_notes'][:50]}..."
            hover_text.append(text)

        # Error bars if available
        error_y = None
        if show_stderr and any(s is not None for s in stderr):
            error_y = dict(
                type='data',
                array=[s if s is not None else 0 for s in stderr],
                visible=True,
            )

        fig.add_trace(go.Scatter(
            x=dates,
            y=scores,
            mode='markers',
            name=provider,
            error_y=error_y,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_text,
            marker=dict(
                size=10,
                opacity=0.7,
                line=dict(width=1, color='white'),
            ),
        ))

    fig.update_layout(
        title=f"{bench_info['name']} Results by Provider",
        xaxis_title="Date",
        yaxis_title=f"Score ({bench_info['unit']})",
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

    # Model family comparison
    st.subheader("Performance by Model Family")

    # Get family stats
    family_stats = results.group_by("family").agg([
        pl.col("score").max().alias("best_score"),
        pl.col("score").mean().alias("avg_score"),
        pl.len().alias("count"),
    ]).filter(pl.col("family").is_not_null()).sort("best_score", descending=True)

    if not family_stats.is_empty():
        fig_family = px.bar(
            family_stats.to_pandas(),
            x="family",
            y="best_score",
            color="avg_score",
            title="Best Score by Model Family",
            labels={"family": "Model Family", "best_score": "Best Score"},
        )
        st.plotly_chart(fig_family, use_container_width=True)

    # Results table
    st.subheader("All Results")

    # Prepare display table
    display_cols = [
        "effective_date", "model_name", "provider", "score",
        "score_stderr", "trust_tier", "source_title"
    ]
    available_cols = [c for c in display_cols if c in results.columns]

    display_df = results.select(available_cols).sort("score", descending=True).to_pandas()
    display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]

    st.dataframe(display_df, hide_index=True, use_container_width=True)

    # Export
    if st.button("📥 Export Results"):
        csv = results.to_pandas().to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            f"{selected_benchmark}_results.csv",
            "text/csv",
        )
