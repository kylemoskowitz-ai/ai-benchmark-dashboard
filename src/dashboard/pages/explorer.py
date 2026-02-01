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
    display_df = display_df.rename(columns={k: v for k, v in col_names.items() if k in display_df.columns})

    # Format score with stderr
    if "Stderr" in display_df.columns and "Score" in display_df.columns:
        display_df["Score"] = display_df.apply(
            lambda r: f"{r['Score']:.2f}" + (f" ± {r['Stderr']:.2f}" if r['Stderr'] and r['Stderr'] == r['Stderr'] else ""),
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

    display_cols = ["benchmark_name", "category", "score", "score_stderr", "trust_tier", "source_title"]
    available_cols = [c for c in display_cols if c in results.columns]

    display_df = results.select(available_cols).to_pandas()

    if "score" in display_df.columns:
        display_df["Score"] = display_df.apply(
            lambda r: f"{r['score']:.2f}" + (f" ± {r['score_stderr']:.2f}" if 'score_stderr' in r and r['score_stderr'] and r['score_stderr'] == r['score_stderr'] else "")
            if r['score'] is not None and r['score'] == r['score'] else "—",
            axis=1
        )

    final_cols = ["benchmark_name", "category", "Score", "trust_tier", "source_title"]
    display_df = display_df[[c for c in final_cols if c in display_df.columns or c == "Score"]]
    display_df.columns = [{"benchmark_name": "Benchmark", "category": "Category", "Score": "Score", "trust_tier": "Tier", "source_title": "Source"}.get(c, c) for c in display_df.columns]

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
