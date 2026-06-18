"""
services/db_utils.py

Shared utilities used by all service modules.
- Custom exceptions so services can signal outcomes without knowing about HTTP
- _close() for safe connection/cursor cleanup
- parse_pagination() for validated page/limit extraction
"""
import logging
import psycopg2
from flask import jsonify

logger = logging.getLogger(__name__)

# ── Custom exceptions ─────────────────────────────────────────────────────────
# Services raise these; routes catch them and map to HTTP status codes.
# This keeps Flask completely out of the service layer.

class ServiceError(Exception):
    """Unexpected server-side error (maps to 500)."""

class ValidationError(Exception):
    """Invalid input supplied by the caller (maps to 400)."""

class NotFoundError(Exception):
    """Requested resource does not exist (maps to 404)."""

class ConflictError(Exception):
    """Request conflicts with current state, e.g. duplicate email (maps to 409)."""

class ForbiddenError(Exception):
    """Caller is authenticated but not authorised (maps to 403)."""

class InsufficientStockError(Exception):
    """Not enough stock to fulfil request (maps to 409)."""


# ── Connection helpers ────────────────────────────────────────────────────────

def close(conn, cursor):
    """Safely close cursor then connection, suppressing close-time errors."""
    try:
        if cursor:
            cursor.close()
    except Exception:
        pass
    try:
        if conn:
            conn.close()
    except Exception:
        pass


# ── Response helper (used only in routes) ────────────────────────────────────

def db_error_response(e, operation="database operation"):
    """
    Log the full psycopg2 error internally and return a sanitised Flask
    response. Called from route exception handlers — never from services.
    """
    logger.error("psycopg2 error during %s: %s", operation, e, exc_info=True)
    return jsonify({"error": f"A server error occurred during {operation}"}), 500


# ── Pagination ────────────────────────────────────────────────────────────────

PAGINATION_MAX_LIMIT     = 100
PAGINATION_DEFAULT_LIMIT = 20


def parse_pagination(args):
    """
    Parse and validate ?page= and ?limit= from a query string dict.
    Returns (page, limit, error_string_or_None).
    """
    try:
        page = int(args.get("page", 1))
        if page < 1:
            return None, None, "page must be a positive integer"
    except (ValueError, TypeError):
        return None, None, "page must be a valid integer"

    try:
        limit = int(args.get("limit", PAGINATION_DEFAULT_LIMIT))
        if limit < 1:
            return None, None, "limit must be a positive integer"
        limit = min(limit, PAGINATION_MAX_LIMIT)
    except (ValueError, TypeError):
        return None, None, "limit must be a valid integer"

    return page, limit, None
