"""Benchmark Explorer page - deep dive into single benchmark."""

import streamlit as st
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

    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found. Run `make update-data` to load data.")
        return

    # Benchmark selector
    benchmark_options = {
        row["benchmark_id"]: row["name"]
        for row in benchmarks.iter_rows(named=True)
    }

    selected_benchmark = st.selectbox(
        "Benchmark",
        options=list(benchmark_options.keys()),
        format_func=lambda x: benchmark_options.get(x, x),
    )

    bench_meta = benchmarks.filter(pl.col("benchmark_id") == selected_benchmark)
    if bench_meta.is_empty():
        st.error("Benchmark not found")
        return

    bench_info = bench_meta.row(0, named=True)

    # Benchmark details - collapsible
    with st.expander("Benchmark details"):
        cols = st.columns(4)
        cols[0].write(f"**Unit:** {bench_info['unit']}")
        cols[1].write(f"**Scale:** {bench_info['scale_min']}–{bench_info['scale_max']}")
        cols[2].write(f"**Higher is better:** {'Yes' if bench_info['higher_is_better'] else 'No'}")
        if bench_info.get("official_url"):
            cols[3].write(f"[Official site]({bench_info['official_url']})")

    st.divider()

    # Filters
    col1, col2, col3 = st.columns(3)

    providers = get_unique_providers()

    with col1:
        selected_providers = st.multiselect(
            "Providers",
            options=providers,
            default=[],
            placeholder="All",
        )

    with col2:
        date_range = st.date_input(
            "Date range",
            value=(date(2024, 1, 1), date.today()),
        )

    with col3:
        trust_filter = st.multiselect(
            "Trust tier",
            options=["A", "B", "C"],
            default=["A", "B", "C"] if not st.session_state.get("official_only") else ["A"],
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
        st.warning("No results found for selected filters.")
        return

    results = results.with_columns([
        pl.coalesce(pl.col("evaluation_date"), pl.col("model_release_date")).alias("effective_date")
    ])

    # Results count
    st.caption(f"{len(results)} results")

    # Chart
    st.markdown("### Results Over Time")

    fig = go.Figure()

    # Color by provider
    colors = ['#4C78A8', '#F58518', '#54A24B', '#E45756', '#72B7B2', '#B279A2', '#FF9DA6', '#9C755F']

    for i, provider in enumerate(results["provider"].unique().to_list()):
        provider_data = results.filter(pl.col("provider") == provider).sort("effective_date")

        fig.add_trace(go.Scatter(
            x=provider_data["effective_date"].to_list(),
            y=provider_data["score"].to_list(),
            mode='markers',
            name=provider,
            marker=dict(size=8, color=colors[i % len(colors)], opacity=0.8),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Score: %{y:.2f}<br>"
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
        xaxis=dict(gridcolor='#f0f0f0', showline=True, linecolor='#ddd'),
        yaxis=dict(gridcolor='#f0f0f0', showline=True, linecolor='#ddd'),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Results table
    st.markdown("### All Results")

    display_df = results.select([
        "effective_date",
        "model_name",
        "provider",
        "score",
        "score_stderr",
        "trust_tier",
        "source_title",
    ]).sort("score", descending=True).to_pandas()

    display_df.columns = ["Date", "Model", "Provider", "Score", "Stderr", "Tier", "Source"]

    # Format score with stderr if available
    display_df["Score"] = display_df.apply(
        lambda r: f"{r['Score']:.2f}" + (f" ± {r['Stderr']:.2f}" if r['Stderr'] else ""),
        axis=1
    )
    display_df = display_df.drop(columns=["Stderr"])

    st.dataframe(display_df, hide_index=True, use_container_width=True)

    # Export
    st.download_button(
        "Export CSV",
        results.to_pandas().to_csv(index=False),
        f"{selected_benchmark}_results.csv",
        "text/csv",
    )
