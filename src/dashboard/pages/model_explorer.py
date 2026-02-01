"""Model Explorer page - all results for a specific model."""

import streamlit as st
import plotly.graph_objects as go
import polars as pl

from src.db.queries import (
    get_all_models,
    get_results_for_model,
    search_models,
    get_unique_providers,
)


def render_model_explorer():
    """Render the model explorer page."""
    st.title("Model Explorer")

    # Search and filter
    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input(
            "Search models",
            placeholder="Model name or provider...",
        )

    with col2:
        provider_filter = st.selectbox(
            "Provider",
            options=["All"] + get_unique_providers(),
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
        "Model",
        options=list(model_options.keys()),
        format_func=lambda x: model_options.get(x, x),
    )

    if not selected_model:
        return

    # Get model info
    model_info = models.filter(pl.col("model_id") == selected_model)
    if model_info.is_empty():
        st.error("Model not found")
        return

    model = model_info.row(0, named=True)

    st.divider()

    # Model header
    st.markdown(f"## {model['name']}")

    cols = st.columns(4)
    cols[0].metric("Provider", model["provider"])
    cols[1].metric("Family", model.get("family") or "—")
    cols[2].metric("Released", str(model.get("release_date")) if model.get("release_date") else "—")
    cols[3].metric("Status", "Verified" if model.get("status", "verified") == "verified" else "Unverified")

    # Get results
    results = get_results_for_model(selected_model)

    if results.is_empty():
        st.warning("No benchmark results found for this model.")
        return

    st.divider()

    # Summary stats
    cols = st.columns(3)
    cols[0].metric("Benchmarks", results["benchmark_name"].n_unique())
    cols[1].metric("Tier A Results", len(results.filter(pl.col("trust_tier") == "A")))
    cols[2].metric("Total Results", len(results))

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
            marker_color='#4C78A8',
            hovertemplate="<b>%{x}</b><br>%{y:.1f}% of max<extra></extra>",
        ))

        fig.update_layout(
            xaxis_title="",
            yaxis_title="% of max score",
            height=350,
            margin=dict(l=40, r=20, t=20, b=100),
            plot_bgcolor='white',
            xaxis=dict(tickangle=-45, gridcolor='#f0f0f0'),
            yaxis=dict(gridcolor='#f0f0f0', range=[0, 105]),
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

    # Format score
    display_df["Score"] = display_df.apply(
        lambda r: f"{r['score']:.2f}" + (f" ± {r['score_stderr']:.2f}" if r['score_stderr'] else "")
        if r['score'] is not None else "—",
        axis=1
    )

    display_df = display_df[["benchmark_name", "category", "Score", "trust_tier", "source_title"]]
    display_df.columns = ["Benchmark", "Category", "Score", "Tier", "Source"]

    st.dataframe(display_df, hide_index=True, use_container_width=True)

    # Export
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

            colors = ['#4C78A8', '#F58518', '#54A24B', '#E45756']
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
                xaxis=dict(tickangle=-45, gridcolor='#f0f0f0'),
                yaxis=dict(gridcolor='#f0f0f0'),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                ),
            )

            st.plotly_chart(fig_compare, use_container_width=True)
