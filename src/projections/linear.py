"""Linear trend projection with uncertainty quantification."""

from datetime import date, timedelta
import numpy as np
from scipy import stats
import polars as pl

from src.models.schemas import ProjectionResult


def linear_projection(
    df: pl.DataFrame,
    score_col: str = "score",
    date_col: str = "effective_date",
    window_months: int = 12,
    forecast_months: int = 12,
    confidence_levels: tuple[float, float] = (0.80, 0.95),
) -> ProjectionResult | None:
    """Fit linear trend on recent data and project forward.

    Uses Ordinary Least Squares with bootstrapped confidence intervals.

    Args:
        df: DataFrame with scores and dates
        score_col: Name of score column
        date_col: Name of date column
        window_months: Months of historical data to use for fitting
        forecast_months: Months to forecast forward
        confidence_levels: Confidence levels for intervals (default: 80%, 95%)

    Returns:
        ProjectionResult with forecasts and confidence intervals,
        or None if insufficient data
    """
    if df.is_empty() or len(df) < 3:
        return None

    # Filter to window and valid scores
    df = df.filter(pl.col(score_col).is_not_null())
    if df.is_empty():
        return None

    # Sort by date
    df = df.sort(date_col)

    # Get date range
    max_date = df[date_col].max()
    if isinstance(max_date, str):
        max_date = date.fromisoformat(max_date)

    min_window_date = max_date - timedelta(days=window_months * 30)

    # Filter to window
    df_window = df.filter(pl.col(date_col) >= min_window_date)

    if len(df_window) < 3:
        return None

    # Convert dates to numeric (days since start)
    dates = df_window[date_col].to_list()
    scores = df_window[score_col].to_list()

    if isinstance(dates[0], str):
        dates = [date.fromisoformat(d) if isinstance(d, str) else d for d in dates]

    start_date = min(dates)
    x = np.array([(d - start_date).days for d in dates])
    y = np.array(scores)

    # Fit linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    # Generate forecast dates
    forecast_dates = []
    current = max_date
    for _ in range(forecast_months):
        current = current + timedelta(days=30)
        forecast_dates.append(current)

    # Forecast values
    forecast_x = np.array([(d - start_date).days for d in forecast_dates])
    forecast_values = intercept + slope * forecast_x

    # Bootstrap for confidence intervals
    n_bootstrap = 1000
    bootstrap_forecasts = np.zeros((n_bootstrap, len(forecast_x)))

    for i in range(n_bootstrap):
        # Resample with replacement
        indices = np.random.choice(len(x), size=len(x), replace=True)
        x_boot = x[indices]
        y_boot = y[indices]

        # Fit on bootstrap sample
        slope_boot, intercept_boot = np.polyfit(x_boot, y_boot, 1)
        bootstrap_forecasts[i] = intercept_boot + slope_boot * forecast_x

    # Calculate confidence intervals
    ci_80_low = np.percentile(bootstrap_forecasts, (1 - confidence_levels[0]) / 2 * 100, axis=0)
    ci_80_high = np.percentile(bootstrap_forecasts, (1 + confidence_levels[0]) / 2 * 100, axis=0)
    ci_95_low = np.percentile(bootstrap_forecasts, (1 - confidence_levels[1]) / 2 * 100, axis=0)
    ci_95_high = np.percentile(bootstrap_forecasts, (1 + confidence_levels[1]) / 2 * 100, axis=0)

    return ProjectionResult(
        benchmark_id=df_window["benchmark_id"][0] if "benchmark_id" in df_window.columns else "unknown",
        method="linear",
        forecast_dates=forecast_dates,
        forecast_values=forecast_values.tolist(),
        ci_80_low=ci_80_low.tolist(),
        ci_80_high=ci_80_high.tolist(),
        ci_95_low=ci_95_low.tolist(),
        ci_95_high=ci_95_high.tolist(),
        fit_window_start=min(dates),
        fit_window_end=max(dates),
        r_squared=r_value ** 2,
        notes=f"Linear trend: {slope:.4f} points/day, R²={r_value**2:.3f}",
    )
