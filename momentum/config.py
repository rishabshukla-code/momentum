"""All settings come from environment variables (or a .env file).

Every partner integration is optional: if its key is blank, Momentum falls back
to a local version so the core loop always runs.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv not installed yet
    pass


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# --- Telegram (required for the live bot) ---
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")

# --- Storage: SQLite by default, SingleStore if a URL is given ---
# SingleStore example: mysql+pymysql://user:pass@host:3306/momentum
DATABASE_URL = _get("DATABASE_URL", "sqlite:///momentum.db")

# --- LLM that writes the nudge text (Arcee, or any OpenAI-compatible API) ---
LLM_BASE_URL = _get("LLM_BASE_URL")  # confirm the exact URL at the Arcee booth
LLM_API_KEY = _get("LLM_API_KEY")
LLM_MODEL = _get("LLM_MODEL")

# --- Superlinked: small task-specific model used to classify excuses ---
SUPERLINKED_URL = _get("SUPERLINKED_URL")
SUPERLINKED_API_KEY = _get("SUPERLINKED_API_KEY")

# --- Cognee memory ---
COGNEE_ENABLED = _get("COGNEE_ENABLED", "false").lower() == "true"

# --- Amplitude analytics ---
AMPLITUDE_API_KEY = _get("AMPLITUDE_API_KEY")

# --- Trigger endpoint (for Guild cron / webhook) ---
TRIGGER_TOKEN = _get("TRIGGER_TOKEN", "change-me")

# --- Nudge pacing ---
# DEMO_MODE shrinks every timer so the loop is visible on stage.
DEMO_MODE = _get("DEMO_MODE", "false").lower() == "true"
NUDGE_GAP_MIN = 1 if DEMO_MODE else int(_get("NUDGE_GAP_MIN", "15"))
RESPONSE_WINDOW_MIN = 1 if DEMO_MODE else int(_get("RESPONSE_WINDOW_MIN", "15"))
MAX_NUDGES_PER_BLOCK = int(_get("MAX_NUDGES_PER_BLOCK", "3"))
QUIET_START_HOUR = int(_get("QUIET_START_HOUR", "23"))
QUIET_END_HOUR = int(_get("QUIET_END_HOUR", "8"))
