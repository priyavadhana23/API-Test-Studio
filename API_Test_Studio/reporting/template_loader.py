"""
reporting/template_loader.py
==============================
Jinja2 template environment loader.

Provides a single ``TemplateLoader`` class that locates the ``templates/``
directory, configures the Jinja2 ``Environment`` with safe defaults, and
exposes a ``render()`` method used by every HTML generator.

Templates must contain NO business logic. They receive pre-computed data
via the template context and render it — nothing else.

Custom filters registered here:
    fmt_float(v, n)     — format float to n decimal places (default 2)
    fmt_ms(v)           — format milliseconds, e.g. "1 234.5 ms"
    fmt_pct(v)          — format percentage, e.g. "94.3%"
    rating_class(r)     — CSS class from health rating string
    status_class(s)     — CSS class from validation status string
    truncate_url(u, n)  — truncate long URLs to n chars (default 40)
"""

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from jinja2 import (
        Environment,
        FileSystemLoader,
        select_autoescape,
        TemplateNotFound,
    )
    _JINJA2_OK = True
except ImportError:
    _JINJA2_OK = False

from utilities.logger import get_logger

logger = get_logger(__name__)

# Default templates directory — two levels up from this file → project root
_DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class TemplateLoader:
    """
    Jinja2 environment factory for the Reporting Engine.

    Args:
        templates_dir: Path to the directory containing ``.html`` templates.
                       Defaults to ``<project_root>/templates/``.

    Usage::

        loader = TemplateLoader()
        html = loader.render("dashboard.html", bundle=report_bundle)
    """

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
    ) -> None:
        self._templates_dir = templates_dir or _DEFAULT_TEMPLATES_DIR
        self._env: Optional[Any] = None

        if not _JINJA2_OK:
            logger.error("TemplateLoader: jinja2 is not installed.")
            return

        if not self._templates_dir.is_dir():
            logger.warning(
                "TemplateLoader: templates directory not found at '%s'. "
                "Creating it.", self._templates_dir,
            )
            self._templates_dir.mkdir(parents=True, exist_ok=True)

        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._register_filters()
        logger.debug(
            "TemplateLoader: initialised from '%s'.", self._templates_dir
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def render(self, template_name: str, **context: Any) -> str:
        """
        Render *template_name* with the provided keyword-argument context.

        Args:
            template_name: Filename of the template (e.g. ``"dashboard.html"``).
            **context:     Template variables passed by name.

        Returns:
            Rendered HTML string.

        Raises:
            RuntimeError: If Jinja2 is not available or the template is missing.
        """
        if not _JINJA2_OK or self._env is None:
            raise RuntimeError(
                "TemplateLoader: jinja2 is not available. "
                "Install it with: pip install jinja2"
            )
        try:
            template = self._env.get_template(template_name)
            logger.debug("TemplateLoader: rendering '%s'.", template_name)
            return template.render(**context)
        except TemplateNotFound:
            raise RuntimeError(
                f"TemplateLoader: template '{template_name}' not found "
                f"in '{self._templates_dir}'."
            )

    # ------------------------------------------------------------------ #
    # Custom Jinja2 filters
    # ------------------------------------------------------------------ #

    def _register_filters(self) -> None:
        """Register all custom template filters on the Jinja2 environment."""
        filters = self._env.filters  # type: ignore[union-attr]

        filters["fmt_float"] = lambda v, n=2: (
            f"{float(v):.{n}f}" if v is not None else "—"
        )
        filters["fmt_ms"] = lambda v: (
            f"{float(v):,.1f} ms" if v is not None else "—"
        )
        filters["fmt_pct"] = lambda v: (
            f"{float(v):.1f}%" if v is not None else "—"
        )
        filters["fmt_sec"] = lambda v: (
            f"{float(v):.2f} s" if v is not None else "—"
        )
        filters["rating_class"] = _rating_css_class
        filters["status_class"]  = _status_css_class
        filters["truncate_url"] = lambda u, n=44: (
            (str(u)[:n] + "…") if u and len(str(u)) > n else (u or "—")
        )
        filters["short_id"] = lambda v: str(v)[:16] + "…" if v else "—"

        logger.debug("TemplateLoader: custom filters registered.")


# ---------------------------------------------------------------------------
# Filter helpers (module-level for testability)
# ---------------------------------------------------------------------------

def _rating_css_class(rating: str) -> str:
    """Map health rating string to a CSS class name."""
    mapping = {
        "Excellent":      "badge-excellent",
        "Good":           "badge-good",
        "Needs Attention":"badge-warning",
        "Critical":       "badge-critical",
    }
    return mapping.get(rating, "badge-unknown")


def _status_css_class(status: str) -> str:
    """Map validation status string to a CSS class name."""
    mapping = {
        "passed":  "status-pass",
        "failed":  "status-fail",
        "error":   "status-error",
        "skipped": "status-skip",
        "running": "status-running",
    }
    return mapping.get((status or "").lower(), "status-unknown")
