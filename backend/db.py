# db.py
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
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except OperationalError as e:
        raise RuntimeError(f"Database connection failed: {e}") from e
