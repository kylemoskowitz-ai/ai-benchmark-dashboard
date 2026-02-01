"""Power law projection for AI scaling law modeling."""

from datetime import date, timedelta
import numpy as np
from scipy.optimize import curve_fit
import polars as pl
import warnings

from src.models.schemas import ProjectionResult


def power_law_func(x, a, b, c):
    """Power law function: y = a * x^b + c

    Args:
        x: Time (days from start)
        a: Scaling coefficient
        b: Power exponent (typically < 1 for diminishing returns)
        c: Offset/baseline

    Returns:
        Predicted value
    """
    return a * np.power(x + 1, b) + c  # +1 to avoid x^b when x=0


def power_law_projection(
    df: pl.DataFrame,
    score_col: str = "score",
    date_col: str = "effective_date",
    ceiling: float | None = None,
    window_months: int = 18,
    forecast_months: int = 12,
    confidence_levels: tuple[float, float] = (0.80, 0.95),
) -> ProjectionResult | None:
    """Fit power law model based on AI scaling laws.

    Power laws are commonly observed in AI capabilities as a function of
    compute, data, or time. This model captures sublinear growth patterns.

    Args:
        df: DataFrame with scores and dates
        score_col: Name of score column
        date_col: Name of date column
        ceiling: Optional maximum possible score (will cap projections)
        window_months: Months of historical data for fitting
        forecast_months: Months to forecast forward
        confidence_levels: Confidence levels for intervals

    Returns:
        ProjectionResult with forecasts and confidence intervals,
        or None if fitting fails
    """
    if df.is_empty() or len(df) < 4:
        return None

    # Filter to valid scores
    df = df.filter(pl.col(score_col).is_not_null())
    if len(df) < 4:
        return None

    df = df.sort(date_col)

    # Get date range
    max_date = df[date_col].max()
    if isinstance(max_date, str):
        max_date = date.fromisoformat(max_date)

    min_window_date = max_date - timedelta(days=window_months * 30)
    df_window = df.filter(pl.col(date_col) >= min_window_date)

    if len(df_window) < 4:
        return None

    # Prepare data
    dates = df_window[date_col].to_list()
    scores = df_window[score_col].to_list()

    if isinstance(dates[0], str):
        dates = [date.fromisoformat(d) if isinstance(d, str) else d for d in dates]

    start_date = min(dates)
    x = np.array([(d - start_date).days for d in dates])
    y = np.array(scores)

    # Fit power law model
    try:
        y_range = max(y) - min(y) if max(y) != min(y) else 1.0

        # Initial guesses
        a_init = y_range / (max(x) ** 0.5 + 1)
        b_init = 0.5  # Typical sublinear exponent
        c_init = min(y)

        # Bounds: a > 0, 0 < b < 2, c can be anything
        bounds = (
            [0.0, 0.01, -1000],  # Lower bounds
            [y_range * 10, 2.0, max(y) * 2],  # Upper bounds
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            popt, pcov = curve_fit(
                power_law_func,
                x,
                y,
                p0=[a_init, b_init, c_init],
                bounds=bounds,
                maxfev=5000,
            )

        a_fit, b_fit, c_fit = popt

    except (RuntimeError, ValueError):
        return None

    # Generate forecast dates
    forecast_dates = []
    current = max_date
    for _ in range(forecast_months):
        current = current + timedelta(days=30)
        forecast_dates.append(current)

    forecast_x = np.array([(d - start_date).days for d in forecast_dates])
    forecast_values = power_law_func(forecast_x, a_fit, b_fit, c_fit)

    # Cap forecasts at ceiling if provided
    if ceiling is not None:
        forecast_values = np.minimum(forecast_values, ceiling)

    # Bootstrap for confidence intervals
    n_bootstrap = 500
    bootstrap_forecasts = np.zeros((n_bootstrap, len(forecast_x)))

    for i in range(n_bootstrap):
        indices = np.random.choice(len(x), size=len(x), replace=True)
        x_boot = x[indices]
        y_boot = y[indices]

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                popt_boot, _ = curve_fit(
                    power_law_func,
                    x_boot,
                    y_boot,
                    p0=popt,
                    bounds=bounds,
                    maxfev=2000,
                )
            boot_forecast = power_law_func(forecast_x, *popt_boot)
            if ceiling is not None:
                boot_forecast = np.minimum(boot_forecast, ceiling)
            bootstrap_forecasts[i] = boot_forecast
        except (RuntimeError, ValueError):
            bootstrap_forecasts[i] = forecast_values

    # Calculate confidence intervals
    ci_80_low = np.percentile(bootstrap_forecasts, (1 - confidence_levels[0]) / 2 * 100, axis=0)
    ci_80_high = np.percentile(bootstrap_forecasts, (1 + confidence_levels[0]) / 2 * 100, axis=0)
    ci_95_low = np.percentile(bootstrap_forecasts, (1 - confidence_levels[1]) / 2 * 100, axis=0)
    ci_95_high = np.percentile(bootstrap_forecasts, (1 + confidence_levels[1]) / 2 * 100, axis=0)

    # Cap intervals at ceiling if provided
    if ceiling is not None:
        ci_80_high = np.minimum(ci_80_high, ceiling)
        ci_95_high = np.minimum(ci_95_high, ceiling)

    # Calculate R² for fit quality
    y_pred = power_law_func(x, a_fit, b_fit, c_fit)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    return ProjectionResult(
        benchmark_id=df_window["benchmark_id"][0] if "benchmark_id" in df_window.columns else "unknown",
        method="power_law",
        forecast_dates=forecast_dates,
        forecast_values=forecast_values.tolist(),
        ci_80_low=ci_80_low.tolist(),
        ci_80_high=ci_80_high.tolist(),
        ci_95_low=ci_95_low.tolist(),
        ci_95_high=ci_95_high.tolist(),
        fit_window_start=min(dates),
        fit_window_end=max(dates),
        r_squared=r_squared,
        notes=(
            f"Power law: {a_fit:.2f} * t^{b_fit:.3f} + {c_fit:.1f}, "
            f"R²={r_squared:.3f}"
        ),
    )
