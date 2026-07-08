"""
reporting/chart_generator.py
==============================
Reusable Plotly chart builders for the Reporting Engine.

All functions accept pre-computed data and return an HTML ``<div>`` string.
Pass ``include_js=True`` on the *first* chart of a page to embed Plotly.js
inline (~3 MB), ``include_js="cdn"`` to load from the Plotly CDN instead
(keeps the HTML small), or ``include_js=False`` for every subsequent chart
on the same page (they reuse the already-loaded bundle).

Available chart types:
    generate_pie_chart()           — pass/fail / failure distribution donut
    generate_bar_chart()           — endpoint pass rates, execution counts
    generate_grouped_bar_chart()   — multi-series grouped bar (regression)
    generate_line_chart()          — trend lines with optional moving-average
    generate_histogram()           — response-time frequency distribution
    generate_gauge_chart()         — health score gauge (0–100)
    generate_response_time_chart() — horizontal bar of per-endpoint avg RT
    generate_rt_trend_chart()      — RT over execution order (line)
    generate_regression_chart()    — pass-rate comparison across runs
                                     (placeholder when only one run exists)

No SQL. No analytics calculations. Pure Plotly visualisation.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import plotly.graph_objects as go
    import plotly.offline as pyo
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False

from utilities.logger import get_logger

logger = get_logger(__name__)

# Colour palette — consistent across all charts
_PASS_COLOR   = "#27AE60"
_FAIL_COLOR   = "#E74C3C"
_ERROR_COLOR  = "#E67E22"
_SKIP_COLOR   = "#95A5A6"
_BLUE         = "#2980B9"
_PURPLE       = "#8E44AD"
_DARK         = "#2C3E50"
_LIGHT_BG     = "#F8F9FA"


def _no_plotly_fallback(title: str) -> str:
    """Return a plain HTML message when Plotly is unavailable."""
    return (
        f'<div style="padding:20px;background:#fff3cd;border:1px solid #ffc107;">'
        f'<b>Chart unavailable:</b> {title} — install plotly to enable charts.</div>'
    )


def _to_html(fig: Any, include_js: bool = False) -> str:
    """
    Render a Plotly figure to a self-contained HTML div string.

    Args:
        fig:        Plotly Figure object.
        include_js: ``True`` for the first chart on a page (embeds ~3 MB JS).
                    ``False`` for all subsequent charts.

    Returns:
        HTML string starting with ``<div>``.
    """
    return pyo.plot(
        fig,
        output_type="div",
        include_plotlyjs=include_js,
        config={"responsive": True, "displayModeBar": False},
    )


# ---------------------------------------------------------------------------
# Public chart generators
# ---------------------------------------------------------------------------

def generate_pie_chart(
    labels: List[str],
    values: List[float],
    title: str,
    colors: Optional[List[str]] = None,
    include_js: bool = False,
) -> str:
    """
    Generate a Plotly donut pie chart.

    Args:
        labels:     Slice labels.
        values:     Slice values (will be normalised to percentages).
        title:      Chart title.
        colors:     Optional list of hex colour strings.
        include_js: Embed Plotly.js (True for first chart only).

    Returns:
        HTML ``<div>`` string.
    """
    if not _PLOTLY_OK:
        return _no_plotly_fallback(title)

    default_colors = [_PASS_COLOR, _FAIL_COLOR, _ERROR_COLOR, _SKIP_COLOR, _BLUE]
    chart_colors   = colors or default_colors[: len(labels)]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.40,
        marker=dict(colors=chart_colors, line=dict(color="#fff", width=2)),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_DARK)),
        paper_bgcolor=_LIGHT_BG,
        plot_bgcolor=_LIGHT_BG,
        margin=dict(t=50, b=20, l=20, r=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        height=350,
    )
    logger.debug("ChartGenerator: pie chart '%s' built.", title)
    return _to_html(fig, include_js)


def generate_bar_chart(
    categories: List[str],
    values: List[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
    color: str = _BLUE,
    horizontal: bool = False,
    include_js: bool = False,
) -> str:
    """
    Generate a Plotly bar chart.

    Args:
        categories:  Category axis labels.
        values:      Bar heights.
        title:       Chart title.
        x_label:     X-axis label.
        y_label:     Y-axis label.
        color:       Bar colour hex string.
        horizontal:  When ``True`` produces a horizontal bar chart.
        include_js:  Embed Plotly.js.

    Returns:
        HTML ``<div>`` string.
    """
    if not _PLOTLY_OK:
        return _no_plotly_fallback(title)

    if horizontal:
        trace = go.Bar(
            y=categories, x=values,
            orientation="h",
            marker_color=color,
            hovertemplate="%{y}: %{x}<extra></extra>",
        )
    else:
        trace = go.Bar(
            x=categories, y=values,
            marker_color=color,
            hovertemplate="%{x}: %{y}<extra></extra>",
        )

    fig = go.Figure(trace)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_DARK)),
        xaxis_title=x_label,
        yaxis_title=y_label,
        paper_bgcolor=_LIGHT_BG,
        plot_bgcolor=_LIGHT_BG,
        margin=dict(t=50, b=60, l=60, r=20),
        height=380,
    )
    logger.debug("ChartGenerator: bar chart '%s' built.", title)
    return _to_html(fig, include_js)


def generate_grouped_bar_chart(
    categories: List[str],
    series: List[Tuple[str, List[float], str]],
    title: str,
    x_label: str = "",
    y_label: str = "",
    include_js: bool = False,
) -> str:
    """
    Generate a grouped bar chart with multiple series.

    Args:
        categories: Shared x-axis labels.
        series:     List of ``(name, values, color)`` tuples.
        title:      Chart title.
        include_js: Embed Plotly.js.

    Returns:
        HTML ``<div>`` string.
    """
    if not _PLOTLY_OK:
        return _no_plotly_fallback(title)

    fig = go.Figure()
    for name, vals, clr in series:
        fig.add_trace(go.Bar(
            name=name,
            x=categories,
            y=vals,
            marker_color=clr,
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_DARK)),
        barmode="group",
        xaxis_title=x_label,
        yaxis_title=y_label,
        paper_bgcolor=_LIGHT_BG,
        plot_bgcolor=_LIGHT_BG,
        margin=dict(t=50, b=60, l=60, r=20),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    return _to_html(fig, include_js)


def generate_line_chart(
    x_values: List[str],
    y_values: List[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
    moving_avg: Optional[List[float]] = None,
    color: str = _BLUE,
    include_js: bool = False,
) -> str:
    """
    Generate a Plotly line chart, optionally with a moving-average overlay.

    Args:
        x_values:   X-axis tick labels (e.g. dates).
        y_values:   Primary series data points.
        title:      Chart title.
        x_label:    X-axis label.
        y_label:    Y-axis label.
        moving_avg: Optional moving-average values (same length as y_values).
        color:      Line colour.
        include_js: Embed Plotly.js.

    Returns:
        HTML ``<div>`` string.
    """
    if not _PLOTLY_OK:
        return _no_plotly_fallback(title)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_values, y=y_values,
        mode="lines+markers",
        name="Value",
        line=dict(color=color, width=2),
        marker=dict(size=6),
        hovertemplate="%{x}: %{y:.2f}<extra></extra>",
    ))
    if moving_avg:
        fig.add_trace(go.Scatter(
            x=x_values, y=moving_avg,
            mode="lines",
            name="Moving Avg",
            line=dict(color=_PURPLE, width=1.5, dash="dash"),
            hovertemplate="MA: %{y:.2f}<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=_DARK)),
        xaxis_title=x_label,
        yaxis_title=y_label,
        paper_bgcolor=_LIGHT_BG,
        plot_bgcolor=_LIGHT_BG,
        margin=dict(t=50, b=60, l=60, r=20),
        height=350,
    )
    logger.debug("ChartGenerator: line chart '%s' built.", title)
    return _to_html(fig, include_js)


def generate_gauge_chart(
    value: float,
    title: str,
    min_val: float = 0,
    max_val: float = 100,
    thresholds: Optional[List[Tuple[float, str]]] = None,
    include_js: bool = False,
) -> str:
    """
    Generate a Plotly gauge chart for the health score.

    Args:
        value:      Current gauge value.
        title:      Chart title.
        min_val:    Minimum of the gauge range.
        max_val:    Maximum of the gauge range.
        thresholds: List of ``(value, colour)`` threshold steps.
        include_js: Embed Plotly.js.

    Returns:
        HTML ``<div>`` string.
    """
    if not _PLOTLY_OK:
        return _no_plotly_fallback(title)

    default_thresholds = [
        (60,  _FAIL_COLOR),
        (80,  _ERROR_COLOR),
        (95,  "#F1C40F"),
        (100, _PASS_COLOR),
    ]
    steps = thresholds or default_thresholds
    gauge_steps = []
    prev = min_val
    for threshold, colour in steps:
        gauge_steps.append(dict(range=[prev, threshold], color=colour))
        prev = threshold

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title=dict(text=title, font=dict(size=16, color=_DARK)),
        gauge=dict(
            axis=dict(range=[min_val, max_val], tickwidth=1),
            bar=dict(color=_DARK),
            steps=gauge_steps,
            threshold=dict(
                line=dict(color="black", width=3),
                thickness=0.75,
                value=value,
            ),
        ),
        number=dict(suffix=" / 100", font=dict(size=28)),
    ))
    fig.update_layout(
        paper_bgcolor=_LIGHT_BG,
        margin=dict(t=60, b=20, l=30, r=30),
        height=300,
    )
    logger.debug("ChartGenerator: gauge chart '%s' built (value=%.1f).", title, value)
    return _to_html(fig, include_js)


def generate_response_time_chart(
    endpoints: List[str],
    avg_times: List[float],
    title: str = "Average Response Time by Endpoint (ms)",
    include_js: bool = False,
) -> str:
    """
    Generate a horizontal bar chart of per-endpoint response times.

    Args:
        endpoints:  Endpoint path labels.
        avg_times:  Average response time in ms for each endpoint.
        title:      Chart title.
        include_js: Embed Plotly.js.

    Returns:
        HTML ``<div>`` string.
    """
    return generate_bar_chart(
        categories=endpoints,
        values=avg_times,
        title=title,
        y_label="Response Time (ms)",
        color=_BLUE,
        horizontal=True,
        include_js=include_js,
    )
