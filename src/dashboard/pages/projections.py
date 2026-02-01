"""Projections page - trend forecasts with uncertainty."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date
import polars as pl

from src.db.queries import get_all_benchmarks, get_frontier_results
from src.projections.linear import linear_projection
from src.projections.saturation import saturation_projection


DISCLAIMER = """
**Projection Disclaimer**: These projections assume benchmark definitions,
harnesses, and evaluation protocols remain comparable over time. They are
mathematical extrapolations, not forecasts of real-world AI capability.
Past trends may not continue. Use with caution.
"""


def render_projections():
    """Render the projections page."""
    st.title("Benchmark Projections")
    st.caption("Trend forecasts with uncertainty quantification")

    # Disclaimer - always visible
    st.markdown(f"""
    <div class="disclaimer">
    ⚠️ {DISCLAIMER}
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get benchmarks
    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found. Run `make update-data` to load data.")
        return

    # Configuration
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
            "Projection Method",
            options=["linear", "saturation"],
            format_func=lambda x: {
                "linear": "Linear Trend",
                "saturation": "Saturation-Aware (Logistic)",
            }.get(x, x),
        )

    with col3:
        window_months = st.slider(
            "Fitting Window (months)",
            min_value=6,
            max_value=24,
            value=12,
            help="Historical data window for fitting the trend",
        )

    col1, col2 = st.columns(2)

    with col1:
        forecast_months = st.slider(
            "Forecast Horizon (months)",
            min_value=3,
            max_value=24,
            value=12,
        )

    with col2:
        show_ci = st.multiselect(
            "Confidence Intervals",
            options=["80%", "95%"],
            default=["80%", "95%"],
        )

    # Get benchmark metadata
    bench_meta = benchmarks.filter(pl.col("benchmark_id") == selected_benchmark)
    if bench_meta.is_empty():
        st.error("Benchmark not found")
        return

    bench_info = bench_meta.row(0, named=True)
    ceiling = bench_info["scale_max"]

    # Get frontier data
    frontier = get_frontier_results(
        selected_benchmark,
        min_date=date(2023, 1, 1),  # Get more history for fitting
    )

    if frontier.is_empty() or len(frontier) < 5:
        st.warning(
            f"Insufficient data for projections. "
            f"Need at least 5 data points, found {len(frontier)}."
        )
        return

    # Add effective date
    frontier = frontier.with_columns([
        pl.coalesce(pl.col("evaluation_date"), pl.col("model_release_date")).alias("effective_date")
    ])

    # Run projection
    if projection_method == "linear":
        projection = linear_projection(
            frontier,
            window_months=window_months,
            forecast_months=forecast_months,
        )
    else:
        projection = saturation_projection(
            frontier,
            ceiling=ceiling,
            window_months=window_months,
            forecast_months=forecast_months,
        )

    if projection is None:
        st.error("Projection fitting failed. Try a different window or method.")
        return

    # Create visualization
    st.subheader(f"{bench_info['name']} - {projection_method.title()} Projection")

    fig = go.Figure()

    # Historical data
    hist_dates = frontier["effective_date"].to_list()
    hist_scores = frontier["score"].to_list()
    hist_models = frontier["model_name"].to_list()

    fig.add_trace(go.Scatter(
        x=hist_dates,
        y=hist_scores,
        mode='markers+lines',
        name='Historical Frontier',
        marker=dict(size=10, color='#1f77b4'),
        line=dict(width=2, color='#1f77b4'),
        hovertemplate="<b>%{customdata}</b><br>Score: %{y:.1f}<br>Date: %{x}<extra></extra>",
        customdata=hist_models,
    ))

    # Projection line
    fig.add_trace(go.Scatter(
        x=projection.forecast_dates,
        y=projection.forecast_values,
        mode='lines',
        name='Projection',
        line=dict(width=2, color='#ff7f0e', dash='dash'),
        hovertemplate="Projected: %{y:.1f}<br>Date: %{x}<extra></extra>",
    ))

    # 95% confidence interval
    if "95%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_95_high + projection.ci_95_low[::-1],
            fill='toself',
            fillcolor='rgba(255, 127, 14, 0.1)',
            line=dict(color='rgba(255,255,255,0)'),
            name='95% CI',
            hoverinfo='skip',
        ))

    # 80% confidence interval
    if "80%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_80_high + projection.ci_80_low[::-1],
            fill='toself',
            fillcolor='rgba(255, 127, 14, 0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            name='80% CI',
            hoverinfo='skip',
        ))

    # Ceiling line (for saturation model)
    if projection_method == "saturation":
        fig.add_hline(
            y=ceiling,
            line_dash="dot",
            line_color="gray",
            annotation_text=f"Ceiling: {ceiling}",
        )

    fig.update_layout(
        title=f"{projection_method.title()} Projection (R² = {projection.r_squared:.3f})",
        xaxis_title="Date",
        yaxis_title=f"Score ({bench_info['unit']})",
        hovermode="closest",
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Projection details
    with st.expander("📊 Projection Details", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("R² (Fit Quality)", f"{projection.r_squared:.3f}")
            st.caption("Higher = better fit to historical data")

        with col2:
            st.metric("Fitting Window",
                      f"{projection.fit_window_start} to {projection.fit_window_end}")

        with col3:
            final_forecast = projection.forecast_values[-1]
            final_date = projection.forecast_dates[-1]
            st.metric(f"Projected ({final_date})", f"{final_forecast:.1f}")

        if projection.notes:
            st.info(f"**Model Details:** {projection.notes}")

    # Forecast table
    st.subheader("Forecast Values")

    forecast_df = pl.DataFrame({
        "Date": projection.forecast_dates,
        "Projected": projection.forecast_values,
        "80% CI Low": projection.ci_80_low,
        "80% CI High": projection.ci_80_high,
        "95% CI Low": projection.ci_95_low,
        "95% CI High": projection.ci_95_high,
    })

    st.dataframe(
        forecast_df.to_pandas().round(2),
        hide_index=True,
        use_container_width=True,
    )

    # Sensitivity analysis
    st.subheader("Sensitivity Analysis")
    st.caption("How projections change with different fitting windows")

    windows = [6, 9, 12, 15, 18]
    sensitivity_results = []

    for w in windows:
        if projection_method == "linear":
            proj = linear_projection(frontier, window_months=w, forecast_months=6)
        else:
            proj = saturation_projection(frontier, ceiling=ceiling, window_months=w, forecast_months=6)

        if proj:
            sensitivity_results.append({
                "Window (months)": w,
                "6-month Forecast": proj.forecast_values[-1],
                "R²": proj.r_squared,
            })

    if sensitivity_results:
        sensitivity_df = pl.DataFrame(sensitivity_results)
        st.dataframe(
            sensitivity_df.to_pandas().round(3),
            hide_index=True,
            use_container_width=True,
        )

    # Method comparison
    st.subheader("Method Comparison")

    linear_proj = linear_projection(frontier, window_months=window_months, forecast_months=forecast_months)
    sat_proj = saturation_projection(frontier, ceiling=ceiling, window_months=window_months, forecast_months=forecast_months)

    if linear_proj and sat_proj:
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Linear Trend**")
            st.write(f"- 12-month projection: {linear_proj.forecast_values[-1]:.1f}")
            st.write(f"- R²: {linear_proj.r_squared:.3f}")
            st.write(f"- Assumes: Constant rate of improvement")

        with col2:
            st.write("**Saturation-Aware**")
            st.write(f"- 12-month projection: {sat_proj.forecast_values[-1]:.1f}")
            st.write(f"- R²: {sat_proj.r_squared:.3f}")
            st.write(f"- Assumes: Diminishing returns approaching ceiling")

    # Final disclaimer
    st.divider()
    st.markdown(f"""
    <div class="disclaimer">
    {DISCLAIMER}
    </div>
    """, unsafe_allow_html=True)
