"""Model Explorer page - all results for a specific model."""

import streamlit as st
import plotly.express as px
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
    st.caption("View all benchmark results for a specific model")

    # Search/filter
    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input(
            "Search models",
            placeholder="Enter model name or provider...",
        )

    with col2:
        provider_filter = st.selectbox(
            "Filter by provider",
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
        st.info("No models found. Try a different search or run `make update-data`.")
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

    # Get model info
    model_info = models.filter(pl.col("model_id") == selected_model)
    if model_info.is_empty():
        st.error("Model not found")
        return

    model = model_info.row(0, named=True)

    # Model info card
    st.subheader(model["name"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Provider", model["provider"])
    with col2:
        st.metric("Family", model.get("family") or "—")
    with col3:
        release = model.get("release_date")
        st.metric("Released", str(release) if release else "—")
    with col4:
        status = model.get("status", "verified")
        if status == "verified":
            st.metric("Status", "✅ Verified")
        else:
            st.metric("Status", "⚠️ Unverified")

    # Additional metadata
    with st.expander("📋 Model Details", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            if model.get("training_compute_flop"):
                st.write(f"**Training Compute:** {model['training_compute_flop']:.2e} FLOP")
            if model.get("training_compute_notes"):
                st.write(f"**Compute Notes:** {model['training_compute_notes'][:200]}...")
        with col2:
            if model.get("parameter_count"):
                st.write(f"**Parameters:** {model['parameter_count']:.1f}B")

    st.divider()

    # Get all results for this model
    results = get_results_for_model(selected_model)

    if results.is_empty():
        st.warning("No benchmark results found for this model.")
        return

    st.subheader("Benchmark Results")

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Benchmarks Evaluated", results["benchmark_name"].n_unique())
    with col2:
        tier_a = len(results.filter(pl.col("trust_tier") == "A"))
        st.metric("Tier A Results", tier_a)
    with col3:
        avg_percentile = None  # Would need to compute against all models
        st.metric("Results Total", len(results))

    # Results by benchmark - radar/bar chart
    benchmark_scores = results.group_by("benchmark_name").agg([
        pl.col("score").max().alias("best_score"),
        pl.col("scale_max").first().alias("scale_max"),
    ])

    if not benchmark_scores.is_empty():
        # Normalize scores to percentage of max
        benchmark_scores = benchmark_scores.with_columns([
            (pl.col("best_score") / pl.col("scale_max") * 100).alias("normalized_score")
        ])

        fig = px.bar(
            benchmark_scores.sort("normalized_score", descending=True).to_pandas(),
            x="benchmark_name",
            y="normalized_score",
            title="Performance Across Benchmarks (% of max score)",
            labels={"benchmark_name": "Benchmark", "normalized_score": "Score (%)"},
            color="normalized_score",
            color_continuous_scale="Blues",
        )
        fig.update_layout(xaxis_tickangle=-45, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Detailed results table with provenance
    st.subheader("Detailed Results with Provenance")

    for row in results.iter_rows(named=True):
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 1, 1, 2])

            with col1:
                st.write(f"**{row['benchmark_name']}**")
                st.caption(row.get("category", ""))

            with col2:
                score_str = f"{row['score']:.2f}" if row.get("score") is not None else "—"
                if row.get("score_stderr"):
                    score_str += f" ± {row['score_stderr']:.2f}"
                st.write(f"Score: **{score_str}**")

            with col3:
                tier = row.get("trust_tier", "C")
                tier_colors = {"A": "🟢", "B": "🟡", "C": "⚪"}
                st.write(f"{tier_colors.get(tier, '⚪')} Tier {tier}")

            with col4:
                source_url = row.get("source_url", "")
                source_title = row.get("source_title", "Unknown source")
                if source_url:
                    st.write(f"[{source_title}]({source_url})")
                else:
                    st.write(source_title)

            if row.get("evaluation_notes"):
                st.caption(f"📝 {row['evaluation_notes'][:100]}...")

            st.divider()

    # Export
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("📥 Export Model Data"):
            csv = results.to_pandas().to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                f"{selected_model.replace(':', '_')}_results.csv",
                "text/csv",
            )

    # Compare with other models
    st.subheader("Compare Models")

    compare_models = st.multiselect(
        "Select models to compare",
        options=[m for m in model_options.keys() if m != selected_model],
        format_func=lambda x: model_options.get(x, x),
        max_selections=3,
    )

    if compare_models:
        # Get results for comparison models
        all_comparison = [results.with_columns(pl.lit(model["name"]).alias("model_display"))]

        for comp_model_id in compare_models:
            comp_results = get_results_for_model(comp_model_id)
            if not comp_results.is_empty():
                comp_info = models.filter(pl.col("model_id") == comp_model_id)
                comp_name = comp_info["name"][0] if len(comp_info) > 0 else comp_model_id
                comp_results = comp_results.with_columns(
                    pl.lit(comp_name).alias("model_display")
                )
                all_comparison.append(comp_results)

        if len(all_comparison) > 1:
            combined = pl.concat(all_comparison, how="diagonal")

            # Pivot for comparison
            comparison_df = combined.group_by(["benchmark_name", "model_display"]).agg([
                pl.col("score").max().alias("score")
            ]).to_pandas()

            fig_compare = px.bar(
                comparison_df,
                x="benchmark_name",
                y="score",
                color="model_display",
                barmode="group",
                title="Model Comparison",
            )
            fig_compare.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_compare, use_container_width=True)


# Run when loaded as standalone Streamlit page
render_model_explorer()
