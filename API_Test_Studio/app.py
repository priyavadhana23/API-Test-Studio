"""
app.py
======
API Test Studio — Application Entry Point

Phase 1:  Bootstrap (logging, config, directory verification)
Phase 2:  API spec parsing  (ParserManager → ApiSpec)
Phase 3:  Test case generation  (GeneratorManager → List[TestCase])
Phase 4:  HTTP execution  (ExecutionManager → List[ExecutionResult])
Phase 5:  Response validation  (ValidationManager → List[ValidationResult])
Phase 6:  Persistence  (DatabaseManager → SQLite + JSON/CSV exports)
Phase 7:  Analytics  (AnalyticsManager → AnalyticsSummary)
Phase 8:  Reporting  (ReportManager → HTML, PDF, CSV, JSON reports)
"""

import sys
from pathlib import Path
from typing import Any, List, Tuple

# ---------------------------------------------------------------------------
# Project root — must be set BEFORE any internal imports so relative imports
# resolve correctly regardless of the working directory.
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Internal imports (after path is set)
# ---------------------------------------------------------------------------
from configs import Config
from constants.app_constants import AppMeta, FilePaths, LogMessages
from constants.spec_formats import SpecFormatMeta
from utilities.logger import LoggerFactory, get_logger


# ===========================================================================
# PHASE 1 — Bootstrap
# ===========================================================================

def _init_logging(config: Config) -> None:
    """Initialise the logging system from *config*."""
    LoggerFactory.initialize(config.logging, project_root=PROJECT_ROOT)


def _verify_directories(config: Config, logger) -> None:
    """Ensure all required directories exist, creating them if necessary."""
    for dir_name in [
        FilePaths.UPLOADED_SPECS_DIR, FilePaths.REPORTS_DIR,
        FilePaths.HISTORY_DIR,        FilePaths.DATABASE_DIR,
        FilePaths.LOGS_DIR,           FilePaths.SCHEMAS_DIR,
    ]:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            logger.debug(LogMessages.DIR_VERIFIED, dir_path)
        else:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.warning(LogMessages.DIR_CREATED, dir_path)


def _print_startup_banner(config: Config, logger) -> None:
    """Emit the startup summary banner."""
    sep = "=" * 60
    logger.info(sep)
    logger.info("  %s  v%s", config.app_name, config.app_version)
    logger.info("  %s", config.app_description)
    logger.info(sep)
    logger.info("  Active Environment : %s", config.active_environment.name)
    logger.info("  Base URL           : %s",
                config.active_environment.base_url or "Not configured")
    logger.info("  Auth Type          : %s", config.active_environment.auth_type)
    logger.info("  Log Level          : %s", config.logging.level)
    logger.info("  Available Envs     : %s", ", ".join(config.list_environments()))
    logger.info(sep)


def bootstrap() -> Config:
    """
    Run the Phase 1 bootstrap sequence and return the loaded Config.

    Raises:
        SystemExit: On any unrecoverable startup error.
    """
    try:
        config = Config()
    except Exception as exc:
        print(f"[FATAL] Failed to load configuration: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        _init_logging(config)
    except Exception as exc:
        print(f"[FATAL] Failed to initialise logging: {exc}", file=sys.stderr)
        sys.exit(1)

    logger = get_logger(__name__)
    logger.info(LogMessages.APP_INIT_START, AppMeta.NAME, AppMeta.VERSION)

    try:
        _verify_directories(config, logger)
    except Exception as exc:
        logger.error("Directory verification failed: %s", exc, exc_info=True)
        sys.exit(1)

    _print_startup_banner(config, logger)
    logger.info(LogMessages.APP_INIT_SUCCESS, AppMeta.NAME)
    return config


# ===========================================================================
# PHASE 2 — Spec parsing
# ===========================================================================

def _discover_spec_files(specs_dir: Path) -> List[Path]:
    """Return sorted list of spec files (.json/.yaml/.yml) in *specs_dir*."""
    accepted = set(SpecFormatMeta.all_extensions())
    return sorted(
        f for f in specs_dir.iterdir()
        if f.is_file()
        and not f.name.startswith(".")
        and f.suffix.lower() in accepted
    )


def run_parser(config: Config) -> list:
    """
    Parse every spec file in uploaded_specs/ and return the ApiSpec list.

    Returns:
        List of successfully parsed ``ApiSpec`` objects (may be empty).
    """
    from api_parser import ParserManager                  # Phase 2
    from exceptions.parser_exceptions import ParserError  # Phase 2

    logger = get_logger(__name__)
    specs_dir  = PROJECT_ROOT / FilePaths.UPLOADED_SPECS_DIR
    spec_files = _discover_spec_files(specs_dir)

    if not spec_files:
        logger.info(
            "No spec files found in '%s'. "
            "Add a .json / .yaml / .yml file and re-run.", specs_dir,
        )
        return []

    logger.info("─" * 52)
    logger.info("Phase 2 — Spec Parsing  (%d file(s))", len(spec_files))
    logger.info("─" * 52)

    manager = ParserManager()
    parsed: list = []

    for spec_file in spec_files:
        try:
            spec = manager.parse(str(spec_file))
            parsed.append(spec)
        except ParserError as exc:
            logger.error("Parse failed for '%s': %s", spec_file.name, exc)
        except Exception as exc:
            logger.error(
                "Unexpected parse error for '%s': %s",
                spec_file.name, exc, exc_info=True,
            )

    logger.info("─" * 52)
    logger.info("Parsing complete — %d succeeded, %d failed.",
                len(parsed), len(spec_files) - len(parsed))
    return parsed


# ===========================================================================
# PHASE 3 — Test case generation
# ===========================================================================

def run_generator(config: Config, specs: list) -> List[Tuple]:
    """
    Generate test cases for every parsed spec.

    Returns:
        List of ``(ApiSpec, List[TestCase])`` tuples so Phase 4 can
        associate test cases with their parent spec for the summary title.
    """
    from testcase_generator import GeneratorManager  # Phase 3

    if not specs:
        return []

    logger = get_logger(__name__)
    logger.info("─" * 52)
    logger.info("Phase 3 — Test Case Generation")
    logger.info("─" * 52)

    manager = GeneratorManager()
    results: List[Tuple] = []

    for spec in specs:
        try:
            test_cases = manager.generate(spec, config.active_environment)
            logger.info(
                "Generated %d test cases for '%s'.", len(test_cases), spec.title,
            )
            results.append((spec, test_cases))
        except Exception as exc:
            logger.error(
                "Generation failed for '%s': %s", spec.title, exc, exc_info=True,
            )

    return results


# ===========================================================================
# PHASE 4 — HTTP execution
# ===========================================================================

def run_executor(
    config: Config,
    spec_test_pairs: List[Tuple],
) -> List[Tuple]:
    """
    Execute every generated test case and return ExecutionResult lists.

    Imported inside the function so a Phase 4 import error cannot break
    Phases 1–3.

    Args:
        config:          Loaded Config (provides active_environment).
        spec_test_pairs: List of ``(ApiSpec, List[TestCase])`` tuples
                         produced by Phase 3.

    Returns:
        List of ``(ApiSpec, List[TestCase], List[ExecutionResult])`` tuples.
    """
    from executor import ExecutionManager  # Phase 4

    if not spec_test_pairs:
        return []

    logger = get_logger(__name__)
    logger.info("─" * 52)
    logger.info("Phase 4 — HTTP Execution")
    logger.info("─" * 52)

    env_config  = config.active_environment
    all_results: List[Tuple] = []

    for spec, test_cases in spec_test_pairs:
        if not test_cases:
            logger.warning("No test cases for '%s' — skipping execution.", spec.title)
            continue

        # Override base_url from spec if the environment has none configured
        if not env_config.base_url and spec.base_url:
            logger.info(
                "Environment base_url is empty — using spec base_url: %s",
                spec.base_url,
            )
            env_config.base_url = spec.base_url

        timeout = config.get_raw(
            "execution", "default_timeout_seconds", default=30
        )
        verify_ssl = config.get_raw("execution", "verify_ssl", default=True)

        logger.info(
            "Executing %d test cases for '%s'  →  %s",
            len(test_cases), spec.title, env_config.base_url or "(no base URL)",
        )

        with ExecutionManager(
            environment_config=env_config,
            timeout=int(timeout),
            verify_ssl=bool(verify_ssl),
        ) as manager:
            results = manager.run(test_cases, spec_title=spec.title)

        all_results.append((spec, test_cases, results))
        logger.info(
            "Execution complete for '%s' — %d results.",
            spec.title, len(results),
        )

    return all_results


# ===========================================================================
# PHASE 5 — Response validation
# ===========================================================================

def run_validator(
    config: Config,
    execution_triples: List[Tuple],
) -> List[Tuple]:
    """
    Validate every ExecutionResult and return ValidationResult lists.

    Imported inside the function so a Phase 5 import error cannot break
    Phases 1–4.

    Args:
        config:             Loaded Config instance.
        execution_triples:  List of ``(ApiSpec, List[TestCase], List[ExecutionResult])``
                            tuples produced by Phase 4.

    Returns:
        List of ``(ApiSpec, List[TestCase], List[ExecutionResult],
                   List[ValidationResult])`` tuples.
    """
    from validators import ValidationManager  # Phase 5

    if not execution_triples:
        return []

    logger = get_logger(__name__)
    logger.info("─" * 52)
    logger.info("Phase 5 — Response Validation")
    logger.info("─" * 52)

    all_output: List[Tuple] = []

    for spec, test_cases, exec_results in execution_triples:
        if not exec_results:
            logger.warning(
                "No execution results for '%s' — skipping validation.", spec.title
            )
            continue

        logger.info(
            "Validating %d results for '%s'...", len(exec_results), spec.title
        )

        manager = ValidationManager()
        try:
            val_results = manager.validate_all(
                test_cases=test_cases,
                execution_results=exec_results,
                spec_title=spec.title,
            )
            passed  = sum(1 for v in val_results if v.passed)
            failed  = sum(1 for v in val_results if v.failed)
            logger.info(
                "Validation complete for '%s' — %d passed, %d failed.",
                spec.title, passed, failed,
            )
            all_output.append((spec, test_cases, exec_results, val_results))
        except Exception as exc:
            logger.error(
                "Validation failed for '%s': %s", spec.title, exc, exc_info=True,
            )

    return all_output


# ===========================================================================
# PHASE 6 — Persistence
# ===========================================================================

def run_persistence(
    config: Any,
    validation_quads: List[Tuple],
) -> List[str]:
    """
    Persist every completed run (spec + test cases + execution results +
    validation results) to the SQLite database and export JSON + CSV.

    Imported inside the function so a Phase 6 import error cannot break
    Phases 1–5.

    Args:
        config:            Loaded Config instance.
        validation_quads:  List of
                           ``(ApiSpec, List[TestCase], List[ExecutionResult],
                              List[ValidationResult])`` tuples from Phase 5.
    """
    from database import DatabaseManager   # Phase 6

    if not validation_quads:
        get_logger(__name__).warning(
            "run_persistence: nothing to persist — empty input."
        )
        return []

    logger = get_logger(__name__)
    logger.info("─" * 52)
    logger.info("Phase 6 — Persistence")
    logger.info("─" * 52)

    db_path      = str(PROJECT_ROOT / "database" / "api_test_studio.db")
    history_dir  = str(PROJECT_ROOT / "history")

    with DatabaseManager(db_path=db_path, history_dir=history_dir) as db:
        saved_run_ids: List[str] = []
        for spec, test_cases, exec_results, val_results in validation_quads:
            try:
                run_id = db.save_run(
                    spec=spec,
                    test_cases=test_cases,
                    exec_results=exec_results,
                    val_results=val_results,
                    config=config,
                )
                saved_run_ids.append(run_id)
                # Export to JSON and CSV
                json_path = db.export_run_json(run_id)
                csv_path  = db.export_run_csv(run_id)
                logger.info(
                    "Exports written — JSON: %s  CSV: %s",
                    json_path.name if json_path else "—",
                    csv_path.name  if csv_path  else "—",
                )
            except Exception as exc:
                logger.error(
                    "Persistence failed for '%s': %s",
                    spec.title, exc, exc_info=True,
                )

        # Print aggregate statistics after all runs saved
        stats = db.statistics()
        logger.info("─" * 52)
        logger.info("Database statistics: %s", stats)
        logger.info("─" * 52)
        return saved_run_ids


# ===========================================================================
# PHASE 7 — Analytics
# ===========================================================================

def run_analytics(run_ids: List[str]) -> None:
    """
    Run the Analytics Engine against every run saved in Phase 6.

    Reads all data exclusively through ``DatabaseManager`` — never touches
    SQLite or any repository directly.

    Imported inside the function so a Phase 7 import error cannot break
    Phases 1–6.

    Args:
        run_ids: List of run_id strings produced by ``run_persistence()``.
    """
    from analytics import AnalyticsManager    # Phase 7
    from database import DatabaseManager      # Phase 6 (re-used read-only)

    if not run_ids:
        get_logger(__name__).warning(
            "run_analytics: no run IDs provided — skipping analytics."
        )
        return

    logger = get_logger(__name__)
    logger.info("─" * 52)
    logger.info("Phase 7 — Analytics")
    logger.info("─" * 52)

    db_path = str(PROJECT_ROOT / "database" / "api_test_studio.db")

    with DatabaseManager(db_path=db_path) as db:
        analytics = AnalyticsManager(db)
        for run_id in run_ids:
            try:
                summary = analytics.run_analysis(run_id)
                logger.info(
                    "Analytics complete for run '%s' — "
                    "health=%.1f (%s)  trend=%s",
                    run_id[:16],
                    summary.health.score if summary.health else 0,
                    summary.health.rating if summary.health else "—",
                    summary.trend.direction if summary.trend else "—",
                )
            except Exception as exc:
                logger.error(
                    "Analytics failed for run '%s': %s",
                    run_id[:16], exc, exc_info=True,
                )


# ===========================================================================
# PHASE 8 — Reporting
# ===========================================================================

def run_reporting(run_ids: List[str]) -> None:
    """
    Generate HTML, PDF, CSV, and JSON reports for every persisted run.

    Reads exclusively through DatabaseManager and AnalyticsManager.
    Imported inside the function so a Phase 8 import error cannot break
    Phases 1–7.

    Args:
        run_ids: List of run_id strings from ``run_persistence()``.
    """
    from reporting  import ReportManager    # Phase 8
    from analytics  import AnalyticsManager # Phase 7 (re-used)
    from database   import DatabaseManager  # Phase 6 (re-used)

    if not run_ids:
        get_logger(__name__).warning(
            "run_reporting: no run IDs — skipping report generation."
        )
        return

    logger = get_logger(__name__)
    logger.info("─" * 52)
    logger.info("Phase 8 — Reporting")
    logger.info("─" * 52)

    db_path     = str(PROJECT_ROOT / "database" / "api_test_studio.db")
    reports_dir = PROJECT_ROOT / "reports"

    with DatabaseManager(db_path=db_path) as db:
        analytics = AnalyticsManager(db)
        reporter  = ReportManager(
            db_manager        = db,
            analytics_manager = analytics,
            output_dir        = reports_dir,
        )
        for run_id in run_ids:
            try:
                paths = reporter.generate_report(run_id)
                logger.info(
                    "Reports generated for run '%s' — %d file(s).",
                    run_id[:16], len(paths),
                )
                for p in paths:
                    logger.info("  → %s  (%.1f KB)", p.name,
                                p.stat().st_size / 1024)
            except Exception as exc:
                logger.error(
                    "Reporting failed for run '%s': %s",
                    run_id[:16], exc, exc_info=True,
                )


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    # Phase 1 — bootstrap
    cfg = bootstrap()

    # Phase 2 — parse
    parsed_specs = run_parser(cfg)

    # Phase 3 — generate
    spec_test_pairs = run_generator(cfg, parsed_specs)

    # Phase 4 — execute
    execution_triples = run_executor(cfg, spec_test_pairs)

    # Phase 5 — validate
    validation_quads = run_validator(cfg, execution_triples)

    # Phase 6 — persist
    saved_run_ids = run_persistence(cfg, validation_quads)

    # Phase 7 — analytics
    run_analytics(saved_run_ids)

    # Phase 8 — reports
    run_reporting(saved_run_ids)
