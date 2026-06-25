import os
import logging
from urllib.parse import parse_qs, unquote, urlparse
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logger = logging.getLogger(__name__)

# ── Database ──────────────────────────────────────────────────────────────────

database_url = os.getenv("DATABASE_URL")

if database_url:
    parsed = urlparse(database_url)
    query = parse_qs(parsed.query or "")
    DB_CONFIG = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") or None,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
    }

    # Preserve sslmode from DATABASE_URL query string when present.
    if query.get("sslmode"):
        DB_CONFIG["sslmode"] = query["sslmode"][0]
else:
    DB_CONFIG = {
        "host":     os.getenv("DB_HOST", "localhost"),
        "port":     int(os.getenv("DB_PORT", 5432)),
        "database": os.getenv("DB_NAME"),
        "user":     os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }

db_sslmode = os.getenv("DB_SSLMODE")
if db_sslmode:
    DB_CONFIG["sslmode"] = db_sslmode

# ── JWT ───────────────────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET")

# ── Startup validation ────────────────────────────────────────────────────────
# Fail loud and early — a missing variable surfaces here at import time,
# not silently at the first request with a cryptic DB error.

_REQUIRED = {
    "DB_NAME":     DB_CONFIG["database"],
    "DB_USER":     DB_CONFIG["user"],
    "DB_PASSWORD": DB_CONFIG["password"],
    "JWT_SECRET":  JWT_SECRET,
}

_missing = [k for k, v in _REQUIRED.items() if not v]
if _missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(_missing)}. "
        "Check your .env file."
    )

if len(JWT_SECRET) < 32:
    logger.warning(
        "JWT_SECRET is shorter than 32 characters. "
        "Use a long random secret in production."
    )
