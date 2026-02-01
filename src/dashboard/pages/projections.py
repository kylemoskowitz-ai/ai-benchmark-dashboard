"""Projections page - mathematical forecasting laboratory."""

import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta
import polars as pl
import numpy as np

from src.db.queries import get_all_benchmarks, get_frontier_results
from src.projections.linear import linear_projection
from src.projections.saturation import saturation_projection


def render_projections():
    """Render the projections page."""

    st.markdown("## Projections")

    st.markdown("""
    <div style="background: #FFFEF5; border-left: 3px solid #B8860B; padding: 0.75rem 1rem; margin: 1rem 0; font-size: 0.9rem; color: #665C00;">
    These projections are mathematical extrapolations assuming stable benchmark definitions.
    They are not forecasts of real-world AI capability. Past trends may not continue.
    </div>
    """, unsafe_allow_html=True)

    benchmarks = get_all_benchmarks()

    if benchmarks.is_empty():
        st.warning("No benchmarks found.")
        return

    st.divider()

    # Configuration columns
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
            "Fitting Method",
            options=["linear", "saturation", "ensemble"],
            format_func=lambda x: {
                "linear": "Linear Extrapolation",
                "saturation": "Logistic (Saturation)",
                "ensemble": "Ensemble (Compare All)",
            }.get(x),
        )

    with col3:
        forecast_months = st.slider("Forecast Horizon (months)", 6, 36, 18)

    col1, col2, col3 = st.columns(3)

    with col1:
        window_months = st.slider("Fitting Window (months)", 6, 36, 18)

    with col2:
        show_ci = st.multiselect(
            "Confidence Intervals",
            ["80%", "95%"],
            default=["80%", "95%"],
        )

    with col3:
        show_residuals = st.checkbox("Show Residuals", value=False)

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

    st.divider()

    # Run projections
    projections = {}

    if projection_method == "ensemble" or projection_method == "linear":
        projections["linear"] = linear_projection(
            frontier,
            window_months=window_months,
            forecast_months=forecast_months
        )

    if projection_method == "ensemble" or projection_method == "saturation":
        projections["saturation"] = saturation_projection(
            frontier,
            ceiling=ceiling,
            window_months=window_months,
            forecast_months=forecast_months
        )

    # Filter out failed projections
    projections = {k: v for k, v in projections.items() if v is not None}

    if not projections:
        st.error("All projection methods failed. Try different parameters or more data.")
        return

    # Select primary projection for display
    if projection_method == "ensemble":
        # Use the one with best R²
        primary_method = max(projections.keys(), key=lambda k: projections[k].r_squared or 0)
    else:
        primary_method = projection_method

    projection = projections.get(primary_method)

    if projection is None:
        st.error(f"{primary_method} projection failed. Try different parameters.")
        return

    # Main chart
    st.markdown(f"### {bench_info['name']} Projection")

    fig = go.Figure()

    # Historical data
    fig.add_trace(go.Scatter(
        x=frontier["effective_date"].to_list(),
        y=frontier["score"].to_list(),
        mode='markers+lines',
        name='Historical',
        marker=dict(size=8, color='#4C5C78'),
        line=dict(width=2, color='#4C5C78'),
        hovertemplate="<b>%{customdata}</b><br>Score: %{y:.1f}<extra></extra>",
        customdata=frontier["model_name"].to_list(),
    ))

    # Primary projection line
    fig.add_trace(go.Scatter(
        x=projection.forecast_dates,
        y=projection.forecast_values,
        mode='lines',
        name=f'Projection ({primary_method.title()})',
        line=dict(width=2, color='#B8860B', dash='dash'),
    ))

    # Confidence intervals
    if "95%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_95_high + projection.ci_95_low[::-1],
            fill='toself',
            fillcolor='rgba(184, 134, 11, 0.1)',
            line=dict(color='rgba(255,255,255,0)'),
            name='95% CI',
            hoverinfo='skip',
        ))

    if "80%" in show_ci:
        fig.add_trace(go.Scatter(
            x=projection.forecast_dates + projection.forecast_dates[::-1],
            y=projection.ci_80_high + projection.ci_80_low[::-1],
            fill='toself',
            fillcolor='rgba(184, 134, 11, 0.15)',
            line=dict(color='rgba(255,255,255,0)'),
            name='80% CI',
            hoverinfo='skip',
        ))

    # Ensemble: show other methods as lighter lines
    if projection_method == "ensemble":
        other_colors = {"linear": "#6B8E9F", "saturation": "#8B7355"}
        for method, proj in projections.items():
            if method != primary_method:
                fig.add_trace(go.Scatter(
                    x=proj.forecast_dates,
                    y=proj.forecast_values,
                    mode='lines',
                    name=f'{method.title()}',
                    line=dict(width=1.5, color=other_colors.get(method, '#888'), dash='dot'),
                    opacity=0.7,
                ))

    # Ceiling line for saturation model
    if primary_method == "saturation" or projection_method == "ensemble":
        fig.add_hline(
            y=ceiling,
            line_dash="dot",
            line_color="#999",
            annotation_text=f"Max: {ceiling}",
            annotation_position="right",
        )

    fig.update_layout(
        xaxis_title="",
        yaxis_title=f"Score ({bench_info['unit']})",
        height=450,
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

    # Fit diagnostics
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Method", primary_method.title())
    col2.metric("R² (fit quality)", f"{projection.r_squared:.3f}" if projection.r_squared else "—")
    col3.metric("Fitting Window", f"{projection.fit_window_start} → {projection.fit_window_end}")
    col4.metric(
        f"Projected ({projection.forecast_dates[-1]})",
        f"{projection.forecast_values[-1]:.1f}"
    )

    # Ensemble comparison table
    if projection_method == "ensemble" and len(projections) > 1:
        st.divider()
        st.markdown("### Model Comparison")

        comparison_data = []
        for method, proj in projections.items():
            comparison_data.append({
                "Method": method.title(),
                "R²": f"{proj.r_squared:.3f}" if proj.r_squared else "—",
                "12-mo Forecast": f"{proj.forecast_values[min(11, len(proj.forecast_values)-1)]:.1f}",
                "Final Forecast": f"{proj.forecast_values[-1]:.1f}",
            })

        st.dataframe(comparison_data, hide_index=True, use_container_width=True)

    st.divider()

    # Time-to-threshold calculator
    st.markdown("### Time-to-Threshold Calculator")

    col1, col2 = st.columns(2)

    with col1:
        threshold = st.slider(
            f"Target score for {bench_info['name']}",
            min_value=int(bench_info["scale_min"]),
            max_value=int(bench_info["scale_max"]),
            value=min(90, int(ceiling * 0.9)),
        )

    with col2:
        # Find when projection crosses threshold
        forecast_values = np.array(projection.forecast_values)
        forecast_dates = projection.forecast_dates

        crossing_idx = np.where(forecast_values >= threshold)[0]

        if len(crossing_idx) > 0:
            crossing_date = forecast_dates[crossing_idx[0]]

            # Find CI crossings
            ci_80_low_cross = np.where(np.array(projection.ci_80_low) >= threshold)[0]
            ci_80_high_cross = np.where(np.array(projection.ci_80_high) >= threshold)[0]

            late_date = forecast_dates[ci_80_low_cross[0]] if len(ci_80_low_cross) > 0 else "Beyond forecast"
            early_date = forecast_dates[ci_80_high_cross[0]] if len(ci_80_high_cross) > 0 else crossing_date

            st.metric(
                f"Projected to reach {threshold}",
                str(crossing_date),
                delta=f"80% CI: {early_date} – {late_date}" if isinstance(late_date, date) else None,
            )
        else:
            current_max = frontier["score"].max()
            if current_max >= threshold:
                st.success(f"Already achieved! Current best: {current_max:.1f}")
            else:
                st.info(f"Not projected to reach {threshold} within forecast horizon.")

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

    st.download_button(
        "Export Forecast (CSV)",
        forecast_df.to_pandas().to_csv(index=False),
        f"{selected_benchmark}_forecast.csv",
        "text/csv",
    )
