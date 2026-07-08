"""
web_dashboard/backend/config/settings.py
=========================================
Backend configuration wrapper.

Reads from the existing framework Config (configs/config_loader.py) so
there is exactly ONE source of truth for all settings.  The backend
never duplicates config.yaml values — it delegates to Config.

Usage:
    from web_dashboard.backend.config.settings import get_settings

    settings = get_settings()
    print(settings.app_version)
    print(settings.db_path)
"""

from functools import lru_cache
from pathlib import Path
from typing import List

# ── Locate the project root (two levels up from this file) ──────────────────
# web_dashboard/backend/config/settings.py
#   → backend/config  → backend  → web_dashboard  → API_Test_Studio (root)
_THIS_FILE   = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent.parent.parent   # API_Test_Studio/


class Settings:
    """
    Typed settings object populated from the existing Config system.

    All values are read once at construction time and cached.  Do not
    instantiate directly — use ``get_settings()`` for the shared singleton.
    """

    def __init__(self) -> None:
        # Dynamically add the project root to sys.path so the framework
        # packages (configs, database, analytics, …) are importable when
        # the backend is started from any working directory.
        import sys
        root_str = str(_PROJECT_ROOT)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        from configs.config_loader import Config
        from constants.app_constants import AppMeta

        cfg = Config()

        # ── Application identity ─────────────────────────────────────
        self.app_name: str         = AppMeta.NAME
        self.app_version: str      = AppMeta.VERSION
        self.app_description: str  = AppMeta.DESCRIPTION
        self.framework_version: str = AppMeta.VERSION

        # ── Database ─────────────────────────────────────────────────
        db_dir = _PROJECT_ROOT / cfg.get_path("database")
        self.db_path: str = str(db_dir / "api_test_studio.db")

        # ── Reports / history directories ────────────────────────────
        self.reports_dir: str = str(_PROJECT_ROOT / cfg.get_path("reports"))
        self.history_dir: str = str(_PROJECT_ROOT / cfg.get_path("history"))

        # ── CORS ─────────────────────────────────────────────────────
        # Allow localhost dev origins by default; override via env var
        # CORS_ORIGINS="http://host1,http://host2" in production.
        import os
        cors_env = os.environ.get("CORS_ORIGINS", "")
        if cors_env:
            self.cors_origins: List[str] = [o.strip() for o in cors_env.split(",")]
        else:
            self.cors_origins = [
                "http://localhost",
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:8080",
                "http://127.0.0.1",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:8080",
            ]

        # ── Server defaults ──────────────────────────────────────────
        self.host: str  = os.environ.get("BACKEND_HOST", "127.0.0.1")
        self.port: int  = int(os.environ.get("BACKEND_PORT", "8000"))
        self.reload: bool = os.environ.get("BACKEND_RELOAD", "true").lower() == "true"
        self.log_level: str = cfg.logging.level.lower()

        # ── Project root (for dependency injection) ──────────────────
        self.project_root: Path = _PROJECT_ROOT

        # ── Logging config (forwarded to LoggerFactory) ──────────────
        self.logging_cfg = cfg.logging

    def __repr__(self) -> str:
        return (
            f"Settings(app={self.app_name!r}, version={self.app_version!r}, "
            f"db={self.db_path!r}, host={self.host}:{self.port})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the shared Settings singleton.

    Uses ``lru_cache`` so the framework Config is only loaded once per
    process, even when ``get_settings`` is called from multiple FastAPI
    dependency injections.
    """
    return Settings()
