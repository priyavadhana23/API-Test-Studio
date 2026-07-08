"""
reporting/json_generator.py
=============================
Exports the complete structured execution report as a single JSON file.

The JSON output mirrors the ReportBundle structure so any downstream system
(dashboard, API, future AI layer) can consume it without reading the database.

Structure:
    {
      "metadata":            { … },
      "executive_summary":   { … },
      "analytics": {
        "health":            { … },
        "endpoint_analysis": { … },
        "response_time":     { … },
        "failure_analysis":  { … },
        "regression":        { … },
        "trend":             { … }
      },
      "test_results":        [ … ],
      "validation_details":  [ … ],
      "generated_at":        "…"
    }

No calculations. No SQL. Reads from ReportBundle only.
"""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reporting.report_models import ReportBundle
from utilities.logger import get_logger

logger = get_logger(__name__)


def _serialise(obj: Any) -> Any:
    """
    Recursive JSON serialiser that handles dataclasses, datetimes, etc.

    Args:
        obj: Any Python object.

    Returns:
        JSON-serialisable representation.
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialise(v) for k, v in asdict(obj).items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [_serialise(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    return obj


class JSONGenerator:
    """
    Serialises a ``ReportBundle`` to a structured JSON file.

    Args:
        output_dir: Directory where the JSON file is written.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        logger.debug("JSONGenerator: output_dir='%s'", output_dir)

    def generate(
        self,
        bundle: ReportBundle,
        filename: str = "Execution_Report.json",
    ) -> Path:
        """
        Serialise *bundle* to JSON and write to *output_dir/filename*.

        Args:
            bundle:   Fully assembled ``ReportBundle``.
            filename: Output filename.

        Returns:
            Path to the written JSON file.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / filename

        # Build the output payload
        analytics = bundle.analytics
        payload: dict = {
            "metadata":           _serialise(bundle.metadata),
            "executive_summary":  _serialise(bundle.executive_summary),
            "analytics": {
                "health":            _serialise(getattr(analytics, "health", None)),
                "endpoint_analysis": _serialise(getattr(analytics, "endpoint_analysis", None)),
                "response_time":     _serialise(getattr(analytics, "response_time", None)),
                "failure_analysis":  _serialise(getattr(analytics, "failure_analysis", None)),
                "regression":        _serialise(getattr(analytics, "regression", None)),
                "trend":             _serialise(getattr(analytics, "trend", None)),
            },
            "test_results": [
                {f: getattr(r, f, None) for f in [
                    "result_id", "run_id", "test_id", "operation_id",
                    "endpoint", "http_method", "category", "request_url",
                    "response_status_code", "response_time_ms",
                    "validation_status", "failure_reason",
                    "validation_time_ms", "executed_at",
                ]}
                for r in (bundle.raw_tc_results or [])
            ],
            "validation_details": [
                {f: getattr(d, f, None) for f in [
                    "validation_detail_id", "result_id", "run_id",
                    "validator_name", "status", "message",
                    "severity", "execution_time_ms", "recorded_at",
                ]}
                for d in (bundle.raw_val_details or [])
            ],
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        output_path.write_text(
            json.dumps(payload, default=str, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        size_kb = round(output_path.stat().st_size / 1024, 1)
        logger.info(
            "JSONGenerator: report written → '%s'  (%.1f KB)",
            output_path.name, size_kb,
        )
        return output_path
