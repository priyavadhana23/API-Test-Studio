"""
analytics/statistics.py
========================
Pure, stateless statistical calculation functions.

No imports from other project modules — this is intentionally a leaf
module with zero internal dependencies.  Every analyzer in Phase 7
imports from here rather than reimplementing the same calculations.

Functions:
    mean, median, mode, variance, std_dev
    percentile, p95, p99
    moving_average
    trend_slope   (linear regression slope via least-squares)
    trend_direction (human label: "improving" / "declining" / "stable")
    safe_divide
"""

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def _require_non_empty(values: List[float], fn: str) -> None:
    if not values:
        raise ValueError(f"{fn}() requires a non-empty list.")


# ---------------------------------------------------------------------------
# Central tendency
# ---------------------------------------------------------------------------

def mean(values: List[float]) -> float:
    """
    Arithmetic mean of *values*.

    Args:
        values: Non-empty list of numbers.

    Returns:
        Mean value, rounded to 4 decimal places.

    Raises:
        ValueError: If *values* is empty.
    """
    _require_non_empty(values, "mean")
    return round(sum(values) / len(values), 4)


def median(values: List[float]) -> float:
    """
    Median (50th percentile) of *values*.

    Args:
        values: Non-empty list of numbers.

    Returns:
        Median value.

    Raises:
        ValueError: If *values* is empty.
    """
    _require_non_empty(values, "median")
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return round((s[mid - 1] + s[mid]) / 2, 4)
    return round(s[mid], 4)


def mode(values: List[float]) -> Optional[float]:
    """
    Most frequently occurring value, or ``None`` for an empty list.

    When multiple values share the maximum frequency the smallest is returned
    for deterministic output.

    Args:
        values: List of numbers.

    Returns:
        Mode value, or ``None``.
    """
    if not values:
        return None
    counter = Counter(values)
    max_count = max(counter.values())
    candidates = [v for v, c in counter.items() if c == max_count]
    return min(candidates)


# ---------------------------------------------------------------------------
# Spread
# ---------------------------------------------------------------------------

def variance(values: List[float], population: bool = True) -> float:
    """
    Variance of *values*.

    Args:
        values:     Non-empty list of numbers.
        population: Use population variance (N) when ``True``,
                    sample variance (N-1) when ``False``.

    Returns:
        Variance value.

    Raises:
        ValueError: If *values* is empty (or has <2 elements for sample variance).
    """
    _require_non_empty(values, "variance")
    n = len(values)
    if not population and n < 2:
        raise ValueError("Sample variance requires at least 2 values.")
    m = mean(values)
    sq_diffs = [(v - m) ** 2 for v in values]
    divisor = n if population else (n - 1)
    return round(sum(sq_diffs) / divisor, 6)


def std_dev(values: List[float], population: bool = True) -> float:
    """
    Standard deviation of *values*.

    Args:
        values:     Non-empty list of numbers.
        population: Population (``True``) or sample (``False``) std dev.

    Returns:
        Standard deviation.
    """
    return round(math.sqrt(variance(values, population)), 4)


# ---------------------------------------------------------------------------
# Percentiles
# ---------------------------------------------------------------------------

def percentile(values: List[float], p: float) -> float:
    """
    *p*-th percentile of *values* using nearest-rank method.

    Args:
        values: Non-empty list of numbers.
        p:      Percentile (0–100 inclusive).

    Returns:
        Percentile value.

    Raises:
        ValueError: If *values* is empty or *p* is outside [0, 100].
    """
    _require_non_empty(values, "percentile")
    if not 0 <= p <= 100:
        raise ValueError(f"Percentile must be 0–100, got {p}.")
    s = sorted(values)
    if p == 0:
        return s[0]
    if p == 100:
        return s[-1]
    idx = math.ceil(len(s) * p / 100) - 1
    return round(s[max(0, idx)], 4)


def p95(values: List[float]) -> float:
    """95th percentile of *values*."""
    return percentile(values, 95)


def p99(values: List[float]) -> float:
    """99th percentile of *values*."""
    return percentile(values, 99)


# ---------------------------------------------------------------------------
# Moving average
# ---------------------------------------------------------------------------

def moving_average(values: List[float], window: int = 3) -> List[float]:
    """
    Simple moving average with the given *window* size.

    Positions with insufficient history use the available values only
    (no padding).

    Args:
        values: List of numbers.
        window: Number of preceding values to average (must be ≥ 1).

    Returns:
        List of moving-average values the same length as *values*.

    Raises:
        ValueError: If *window* < 1.
    """
    if window < 1:
        raise ValueError("Moving-average window must be ≥ 1.")
    result: List[float] = []
    for i, _ in enumerate(values):
        slice_ = values[max(0, i - window + 1): i + 1]
        result.append(round(sum(slice_) / len(slice_), 4))
    return result


# ---------------------------------------------------------------------------
# Trend (linear regression slope)
# ---------------------------------------------------------------------------

def trend_slope(values: List[float]) -> float:
    """
    Slope of the least-squares linear regression line through *values*.

    Each value is treated as equally spaced in time (x = 0, 1, 2, …).

    A positive slope indicates an upward (improving for pass-rate or
    worsening for response-time) trend.

    Args:
        values: List of at least 2 numbers.

    Returns:
        Slope (rise per step), rounded to 6 decimal places.
        Returns ``0.0`` for fewer than 2 values.
    """
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = mean([float(x) for x in xs])
    y_mean = mean(values)
    numerator   = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def trend_direction(
    values: List[float],
    threshold: float = 0.01,
) -> str:
    """
    Human-readable trend label based on linear regression slope.

    Args:
        values:    List of measurements over time.
        threshold: Minimum absolute slope to classify as improving/declining.
                   Below *threshold* the trend is "stable".

    Returns:
        One of ``"improving"``, ``"declining"``, or ``"stable"``.
    """
    slope = trend_slope(values)
    if abs(slope) < threshold:
        return "stable"
    return "improving" if slope > 0 else "declining"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Divide *numerator* by *denominator*, returning *default* on zero division.

    Args:
        numerator:   The dividend.
        denominator: The divisor.
        default:     Fallback value (default ``0.0``).

    Returns:
        Division result or *default*.
    """
    if denominator == 0:
        return default
    return numerator / denominator


def frequency_map(items: List[str]) -> Dict[str, int]:
    """
    Count occurrences of each item and return a dict sorted by count desc.

    Args:
        items: List of string labels.

    Returns:
        Dict of ``{label: count}`` sorted by count descending.
    """
    counter = Counter(items)
    return dict(sorted(counter.items(), key=lambda x: x[1], reverse=True))
