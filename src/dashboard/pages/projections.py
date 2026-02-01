"""Projections page - trend forecasts with uncertainty."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date
import polars as pl

from src.db.queries import get_all_benchmarks, get_frontier_results
from src.projections.linear import linear_projection
from src.projections.saturation import saturation_projection


def render_projections():
    """Render the projections page."""
    st.title("Projections")

    # Disclaimer
    st.markdown("""
    <div class="disclaimer">
    These projections are mathematical extrapolations assuming stable benchmark definitions.
    They are not forecasts of real-world AI capability. Past trends may not continue.
    </div>
    """, unsafe_allow_html=True)

    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found.")
        return

    st.divider()

    # Configuration
    col1, col2 = st.columns(2)

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
            "Method",
            options=["linear", "saturation"],
            format_func=lambda x: {"linear": "Linear", "saturation": "Saturation (Logistic)"}.get(x),
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        window_months = st.slider("Fitting window (months)", 6, 24, 12)

    with col2:
        forecast_months = st.slider("Forecast horizon (months)", 3, 24, 12)

    with col3:
        show_ci = st.multiselect("Confidence intervals", ["80%", "95%"], default=["80%", "95%"])

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

    # Run projection
    if projection_method == "linear":
        projection = linear_projection(frontier, window_months=window_months, forecast_months=forecast_months)
    else:
        projection = saturation_projection(frontier, ceiling=ceiling, window_months=window_months, forecast_months=forecast_months)

    if projection is None:
        st.error("Projection failed. Try different parameters.")
        return

    st.divider()

    # Chart
    st.markdown(f"### {bench_info['name']} Projection")

    fig = go.Figure()

    # Historical data
    fig.add_trace(go.Scatter(
        x=frontier["effective_date"].to_list(),
        y=frontier["score"].to_list(),
        mode='markers+lines',
        name='Historical',
        marker=dict(size=8, color='#4C78A8'),
        line=dict(width=2, color='#4C78A8'),
        hovertemplate="<b>%{customdata}</b><br>Score: %{y:.1f}<extra></extra>",
        customdata=frontier["model_name"].to_list(),
    ))

    # Projection
    fig.add_trace(go.Scatter(
        x=projection.forecast_dates,
        y=projection.forecast_values,
        mode='lines',
        name='Projection',
        line=dict(width=2, color='#F58518', dash='dash'),
    ))

    # Confidence intervals
    if "95%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_95_high + projection.ci_95_low[::-1],
            fill='toself',
            fillcolor='rgba(245, 133, 24, 0.1)',
            line=dict(color='rgba(255,255,255,0)'),
            name='95% CI',
            hoverinfo='skip',
        ))

    if "80%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_80_high + projection.ci_80_low[::-1],
            fill='toself',
            fillcolor='rgba(245, 133, 24, 0.15)',
            line=dict(color='rgba(255,255,255,0)'),
            name='80% CI',
            hoverinfo='skip',
        ))

    # Ceiling line for saturation model
    if projection_method == "saturation":
        fig.add_hline(y=ceiling, line_dash="dot", line_color="#999", annotation_text=f"Max: {ceiling}")

    fig.update_layout(
        xaxis_title="",
        yaxis_title=f"Score ({bench_info['unit']})",
        height=420,
        margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        plot_bgcolor='white',
        xaxis=dict(gridcolor='#f0f0f0', showline=True, linecolor='#ddd'),
        yaxis=dict(gridcolor='#f0f0f0', showline=True, linecolor='#ddd'),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Projection details
    cols = st.columns(3)
    cols[0].metric("R² (fit quality)", f"{projection.r_squared:.3f}")
    cols[1].metric("Fitting window", f"{projection.fit_window_start} to {projection.fit_window_end}")
    cols[2].metric(f"Projected ({projection.forecast_dates[-1]})", f"{projection.forecast_values[-1]:.1f}")

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
