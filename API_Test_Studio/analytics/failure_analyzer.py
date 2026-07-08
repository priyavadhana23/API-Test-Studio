"""
analytics/failure_analyzer.py
===============================
Computes failure distribution, top-10 failure messages, and category
breakdowns from test-case results and validation details.

Input:
    tc_results:  List[DbTestCaseResult]
    val_details: List[DbValidationDetail]

Output: FailureAnalysis

No SQL. No HTTP. Pure computation.
"""

from collections import Counter, defaultdict
from typing import Any, List

from analytics.models import FailureAnalysis, FailureEntry
from analytics.statistics import frequency_map, safe_divide
from utilities.logger import get_logger

logger = get_logger(__name__)

# Substrings used to classify failure messages into named buckets
_AUTH_KEYWORDS    = ("401", "403", "unauthorized", "forbidden", "auth", "token")
_TIMEOUT_KEYWORDS = ("timeout", "timed out", "read timeout", "connect timeout")
_SCHEMA_KEYWORDS  = ("schema", "required field", "missing field", "type mismatch")
_BIZRULE_KEYWORDS = ("business rule", "id field", "stack trace", "status field")


class FailureAnalyzer:
    """
    Analyses failure distribution for one execution run.

    Args:
        tc_results:  ``DbTestCaseResult`` rows for the run.
        val_details: ``DbValidationDetail`` rows for the run.
    """

    def __init__(
        self,
        tc_results: List[Any],
        val_details: List[Any],
    ) -> None:
        self._tc       = tc_results
        self._val      = val_details
        logger.debug(
            "FailureAnalyzer: %d results, %d validation details.",
            len(tc_results), len(val_details),
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyse(self) -> FailureAnalysis:
        """
        Compute full failure analysis.

        Returns:
            ``FailureAnalysis`` with all fields populated.
        """
        total = len(self._tc)
        if total == 0:
            return FailureAnalysis()

        # ── Counts from test-case results ──────────────────────────────
        validation_failures = sum(
            1 for r in self._tc
            if (r.validation_status or "").lower() == "failed"
        )
        execution_errors = sum(
            1 for r in self._tc
            if (r.validation_status or "").lower() == "error"
        )
        total_failures = validation_failures + execution_errors

        # ── Classify by failure_reason substrings ──────────────────────
        timeout_count   = 0
        auth_count      = 0
        schema_count    = 0
        biz_rule_count  = 0

        for r in self._tc:
            if not r.failure_reason:
                continue
            msg_lower = r.failure_reason.lower()
            if any(k in msg_lower for k in _TIMEOUT_KEYWORDS):
                timeout_count += 1
            if any(k in msg_lower for k in _AUTH_KEYWORDS):
                auth_count += 1
            if any(k in msg_lower for k in _SCHEMA_KEYWORDS):
                schema_count += 1
            if any(k in msg_lower for k in _BIZRULE_KEYWORDS):
                biz_rule_count += 1

        # ── Top-10 failure messages from validation details ────────────
        all_messages = [
            (v.message or "").strip()
            for v in self._val
            if v.status == "failed" and v.message
        ]
        msg_counts = Counter(all_messages)
        top_failures = [
            FailureEntry(
                category=msg[:120],
                count=count,
                percentage=round(safe_divide(count, total_failures) * 100, 2),
                sample_message=msg[:200],
            )
            for msg, count in msg_counts.most_common(10)
        ]

        # ── Failure distribution by validator name ─────────────────────
        failed_validators = [
            v.validator_name
            for v in self._val
            if v.status == "failed"
        ]
        freq = frequency_map(failed_validators)
        distribution = [
            FailureEntry(
                category=name,
                count=count,
                percentage=round(safe_divide(count, total_failures) * 100, 2),
            )
            for name, count in freq.items()
        ]

        analysis = FailureAnalysis(
            total_failures        = total_failures,
            validation_failures   = validation_failures,
            execution_errors      = execution_errors,
            timeout_failures      = timeout_count,
            auth_failures         = auth_count,
            schema_failures       = schema_count,
            business_rule_failures = biz_rule_count,
            top_failures          = top_failures,
            distribution          = distribution,
        )

        logger.debug(
            "FailureAnalyzer: total=%d  validation=%d  errors=%d  "
            "auth=%d  schema=%d",
            total_failures, validation_failures, execution_errors,
            auth_count, schema_count,
        )
        return analysis
