"""
ORCA Centralized Configuration Service
Safely loads system settings, LLM credentials, database paths, and API timeouts.
Defaults to robust offline deterministic mode when credentials are not configured.
Guarantees 100% path portability across any platform or installation directory.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Base Project Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "orca_sessions.db"

# Load local .env if present (ignored in production/git)
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Centralized configuration container with safe defaults."""

    def __init__(self):
        # LLM Settings
        self.llm_provider: str = (
            os.getenv("LLM_PROVIDER")
            or os.getenv("ORCA_LLM_PROVIDER")
            or "offline"
        ).strip().lower()

        self.llm_model: str = (
            os.getenv("LLM_MODEL")
            or os.getenv("ORCA_LLM_MODEL")
            or "gpt-4o-mini"
        ).strip()

        self.llm_api_key: str = (
            os.getenv("LLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or ""
        ).strip()

        # Operational Settings
        try:
            self.max_replans: int = int(os.getenv("MAX_REPLANS", "3"))
        except ValueError:
            self.max_replans: int = 3

        try:
            self.api_timeout: float = float(os.getenv("API_TIMEOUT", "6.0"))
        except ValueError:
            self.api_timeout: float = 6.0

        custom_db_path = os.getenv("DATABASE_PATH")
        self.database_path: Path = Path(custom_db_path) if custom_db_path else DEFAULT_DB_PATH

        self.project_root: Path = PROJECT_ROOT
        self.data_dir: Path = DATA_DIR

    @property
    def is_llm_enabled(self) -> bool:
        """Returns True only if an active provider and non-empty API key are provided."""
        return self.llm_provider != "offline" and bool(self.llm_api_key)

    def to_dict(self) -> Dict[str, Any]:
        """Returns safe serializable metadata without exposing sensitive keys."""
        return {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_enabled": self.is_llm_enabled,
            "max_replans": self.max_replans,
            "api_timeout": self.api_timeout,
            "database_path": str(self.database_path),
            "project_root": str(self.project_root),
        }


# Global configuration singleton
settings = Settings()
