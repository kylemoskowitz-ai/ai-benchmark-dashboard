"""Saturation-aware projection using logistic growth model."""

from datetime import date, timedelta
import numpy as np
from scipy.optimize import curve_fit
from scipy import stats
import polars as pl
import warnings

from src.models.schemas import ProjectionResult


def logistic_growth(x, L, k, x0):
    """Logistic growth function.

    Args:
        x: Time (days)
        L: Maximum value (ceiling/saturation point)
        k: Growth rate
        x0: Midpoint (inflection point)

    Returns:
        Predicted value
    """
    return L / (1 + np.exp(-k * (x - x0)))


def saturation_projection(
    df: pl.DataFrame,
    score_col: str = "score",
    date_col: str = "effective_date",
    ceiling: float = 100.0,
    window_months: int = 18,
    forecast_months: int = 12,
    confidence_levels: tuple[float, float] = (0.80, 0.95),
) -> ProjectionResult | None:
    """Fit logistic growth model accounting for benchmark saturation.

    The logistic model assumes performance approaches a ceiling over time,
    which is more realistic for benchmarks than unbounded linear growth.

    Args:
        df: DataFrame with scores and dates
        score_col: Name of score column
        date_col: Name of date column
        ceiling: Maximum possible score (saturation point)
        window_months: Months of historical data for fitting
        forecast_months: Months to forecast forward
        confidence_levels: Confidence levels for intervals

    Returns:
        ProjectionResult with forecasts and confidence intervals,
        or None if fitting fails
    """
    if df.is_empty() or len(df) < 5:
        return None

    # Filter to valid scores
    df = df.filter(pl.col(score_col).is_not_null())
    if len(df) < 5:
        return None

    df = df.sort(date_col)

    # Get date range
    max_date = df[date_col].max()
    if isinstance(max_date, str):
        max_date = date.fromisoformat(max_date)

    min_window_date = max_date - timedelta(days=window_months * 30)
    df_window = df.filter(pl.col(date_col) >= min_window_date)

    if len(df_window) < 5:
        return None

    # Prepare data
    dates = df_window[date_col].to_list()
    scores = df_window[score_col].to_list()

    if isinstance(dates[0], str):
        dates = [date.fromisoformat(d) if isinstance(d, str) else d for d in dates]

    start_date = min(dates)
    x = np.array([(d - start_date).days for d in dates])
    y = np.array(scores)

    # Fit logistic model
    try:
        # Initial parameter guesses
        y_max = max(y)
        y_min = min(y)
        x_mid = np.median(x)

        # Estimate initial k (growth rate)
        k_init = 0.01

        # Bounds: L >= max(y), k > 0, x0 can be anywhere
        bounds = (
            [max(y_max, ceiling * 0.5), 1e-6, -1000],  # Lower bounds
            [ceiling * 1.2, 1.0, max(x) + 1000],  # Upper bounds
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            popt, pcov = curve_fit(
                logistic_growth,
                x,
                y,
                p0=[ceiling, k_init, x_mid],
                bounds=bounds,
                maxfev=5000,
            )

        L_fit, k_fit, x0_fit = popt

    except (RuntimeError, ValueError) as e:
        # Fitting failed, return None
        return None

    # Generate forecast dates
    forecast_dates = []
    current = max_date
    for _ in range(forecast_months):
        current = current + timedelta(days=30)
        forecast_dates.append(current)

    forecast_x = np.array([(d - start_date).days for d in forecast_dates])
    forecast_values = logistic_growth(forecast_x, L_fit, k_fit, x0_fit)

    # Cap forecasts at ceiling
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
                    logistic_growth,
                    x_boot,
                    y_boot,
                    p0=popt,
                    bounds=bounds,
                    maxfev=2000,
                )
            bootstrap_forecasts[i] = np.minimum(
                logistic_growth(forecast_x, *popt_boot),
                ceiling
            )
        except (RuntimeError, ValueError):
            # Use original fit if bootstrap fails
            bootstrap_forecasts[i] = forecast_values

    # Calculate confidence intervals
    ci_80_low = np.percentile(bootstrap_forecasts, (1 - confidence_levels[0]) / 2 * 100, axis=0)
    ci_80_high = np.percentile(bootstrap_forecasts, (1 + confidence_levels[0]) / 2 * 100, axis=0)
    ci_95_low = np.percentile(bootstrap_forecasts, (1 - confidence_levels[1]) / 2 * 100, axis=0)
    ci_95_high = np.percentile(bootstrap_forecasts, (1 + confidence_levels[1]) / 2 * 100, axis=0)

    # Cap intervals at ceiling
    ci_80_high = np.minimum(ci_80_high, ceiling)
    ci_95_high = np.minimum(ci_95_high, ceiling)

    # Calculate R² for fit quality
    y_pred = logistic_growth(x, L_fit, k_fit, x0_fit)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    return ProjectionResult(
        benchmark_id=df_window["benchmark_id"][0] if "benchmark_id" in df_window.columns else "unknown",
        method="saturation",
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
            f"Logistic model: ceiling={L_fit:.1f}, "
            f"growth_rate={k_fit:.4f}, R²={r_squared:.3f}"
        ),
    )
