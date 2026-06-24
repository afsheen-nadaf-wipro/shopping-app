# db.py
import os
import psycopg2
from psycopg2 import OperationalError
from config import DB_CONFIG


def get_connection():
    """
    Creates and returns a new PostgreSQL connection using credentials
    from environment variables loaded via config.py.
    Raises a RuntimeError on connection failure to allow callers to handle it.
    """
    try:
        params = dict(DB_CONFIG)

        # Render PostgreSQL requires TLS for external connections.
        # If DB_SSLMODE is not set, default to 'require' for Render hosts.
        if not params.get("sslmode"):
            host = str(params.get("host") or "")
            if "render.com" in host or os.getenv("APP_ENV", "").lower() == "production":
                params["sslmode"] = "require"

        conn = psycopg2.connect(**params)
        return conn
    except OperationalError as e:
        raise RuntimeError(f"Database connection failed: {e}") from e
