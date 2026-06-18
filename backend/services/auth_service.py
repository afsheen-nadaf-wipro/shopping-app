"""
services/auth_service.py

Business logic for user registration and login.
No Flask imports — returns plain Python dicts or raises service exceptions.
"""
import re
import logging
import datetime
import bcrypt
import jwt
import psycopg2

from db import get_connection
from config import JWT_SECRET
from services.db_utils import close, ServiceError, ValidationError, ConflictError, NotFoundError

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")


# ── Validation ────────────────────────────────────────────────────────────────

def validate_register_input(data):
    """
    Validates registration fields.
    Returns (name, email, password) on success, raises ValidationError on failure.
    """
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        raise ValidationError("name, email, and password are required")
    if len(name) > 100:
        raise ValidationError("name must be 100 characters or fewer")
    if not _EMAIL_RE.match(email):
        raise ValidationError("Invalid email format")
    if len(email) > 255:
        raise ValidationError("email must be 255 characters or fewer")
    if len(password) < 6:
        raise ValidationError("Password must be at least 6 characters")
    if len(password) > 72:
        raise ValidationError("Password must be 72 characters or fewer")

    return name, email, password


def validate_login_input(data):
    """Returns (email, password) or raises ValidationError."""
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        raise ValidationError("email and password are required")
    if not _EMAIL_RE.match(email):
        raise ValidationError("Invalid email format")

    return email, password


# ── Service functions ─────────────────────────────────────────────────────────

def register_user(name, email, password):
    """
    Hash password, check for duplicate email, insert user.
    Returns a user dict on success.
    Raises ConflictError if email is taken, ServiceError on DB failure.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            raise ConflictError("Email already registered")

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, 'customer')
            RETURNING id, name, email, role, created_at
            """,
            (name, email, hashed_pw),
        )
        user = cursor.fetchone()
        conn.commit()

    except ConflictError:
        raise
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during register_user: %s", e, exc_info=True)
        raise ServiceError("Registration failed due to a server error")
    except RuntimeError as e:
        logger.error("Connection error during register_user: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return {
        "id":         user[0],
        "name":       user[1],
        "email":      user[2],
        "role":       user[3],
        "created_at": user[4].isoformat(),
    }


def login_user(email, password):
    """
    Verify credentials and return a signed JWT + user info.
    Returns (token, user_dict) on success.
    Raises ValidationError for wrong credentials, ServiceError on DB failure.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, email, password, role FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

    except psycopg2.Error as e:
        logger.error("psycopg2 error during login_user: %s", e, exc_info=True)
        raise ServiceError("Login failed due to a server error")
    except RuntimeError as e:
        logger.error("Connection error during login_user: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    # Intentionally combine not-found and wrong-password into one message
    # to prevent user enumeration attacks
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user[3].encode("utf-8")):
        raise ValidationError("Invalid email or password")

    token = jwt.encode(
        {
            "sub":   str(user[0]),
            "email": user[2],
            "role":  user[4],
            "exp":   datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    return token, {
        "id":   user[0],
        "name": user[1],
        "role": user[4],
    }


# ── Profile validation ────────────────────────────────────────────────────────

def validate_profile_update(data):
    """
    Validates profile update fields.
    Only fields explicitly present in the request are included — a missing
    field is never defaulted and never overwrites the existing DB value.
    `role` is intentionally absent from this validator — it can never be
    updated through the profile endpoint regardless of what the client sends.
    Returns a fields dict or raises ValidationError.
    """
    fields = {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise ValidationError("name cannot be empty")
        if len(name) > 100:
            raise ValidationError("name must be 100 characters or fewer")
        fields["name"] = name

    if "email" in data:
        email = (data["email"] or "").strip().lower()
        if not email:
            raise ValidationError("email cannot be empty")
        if not _EMAIL_RE.match(email):
            raise ValidationError("Invalid email format")
        if len(email) > 255:
            raise ValidationError("email must be 255 characters or fewer")
        fields["email"] = email

    if not fields:
        raise ValidationError("at least one field (name or email) must be provided")

    return fields


def validate_change_password(data):
    """
    Validates change-password payload.
    Both fields must be explicitly present — no silent defaults.
    Returns (current_password, new_password) or raises ValidationError.
    """
    if "current_password" not in data:
        raise ValidationError("current_password is required")
    if "new_password" not in data:
        raise ValidationError("new_password is required")

    current_password = data["current_password"] or ""
    new_password     = data["new_password"] or ""

    if not current_password:
        raise ValidationError("current_password cannot be empty")
    if len(new_password) < 6:
        raise ValidationError("new_password must be at least 6 characters")
    if len(new_password) > 72:
        raise ValidationError("new_password must be 72 characters or fewer")
    if current_password == new_password:
        raise ValidationError("new_password must be different from current password")

    return current_password, new_password


# ── Profile service functions ─────────────────────────────────────────────────

def get_profile(user_id):
    """
    Fetches a user's profile by ID.
    Never selects the password column.
    Returns a profile dict or raises NotFoundError / ServiceError.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        # Explicitly name columns — never SELECT * to avoid leaking password hash
        cursor.execute(
            "SELECT id, name, email, role, created_at FROM users WHERE id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
    except psycopg2.Error as e:
        logger.error("psycopg2 error during get_profile: %s", e, exc_info=True)
        raise ServiceError("A server error occurred while fetching profile")
    except RuntimeError as e:
        logger.error("Connection error during get_profile: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    if not row:
        raise NotFoundError("User not found")

    return {
        "id":         row[0],
        "name":       row[1],
        "email":      row[2],
        "role":       row[3],
        "created_at": row[4].isoformat(),
    }


def update_profile(user_id, fields):
    """
    Updates name and/or email for a user.
    Email uniqueness check uses AND id != %s to exclude the user's own record.
    Role is never in `fields` — enforced at the validator level.
    Returns updated profile dict or raises ConflictError / ServiceError.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        # Duplicate email check — exclude the requesting user's own record
        if "email" in fields:
            cursor.execute(
                "SELECT id FROM users WHERE email = %s AND id != %s",
                (fields["email"], user_id)
            )
            if cursor.fetchone():
                raise ConflictError("Email is already in use by another account")

        # Build SET clause from whitelisted fields only
        # Column names come from the validated fields dict keys — never from
        # raw user input — so no injection risk
        set_clause = ", ".join(f"{col} = %s" for col in fields)
        values     = list(fields.values()) + [user_id]

        cursor.execute(
            f"UPDATE users SET {set_clause} WHERE id = %s "
            "RETURNING id, name, email, role, created_at",
            values
        )
        row = cursor.fetchone()
        conn.commit()

    except ConflictError:
        raise
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during update_profile: %s", e, exc_info=True)
        raise ServiceError("A server error occurred while updating profile")
    except RuntimeError as e:
        logger.error("Connection error during update_profile: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return {
        "id":         row[0],
        "name":       row[1],
        "email":      row[2],
        "role":       row[3],
        "created_at": row[4].isoformat(),
    }


def change_password(user_id, current_password, new_password):
    """
    Verifies the current password then replaces it with a bcrypt hash
    of the new password.
    Raises ValidationError if current password is wrong.
    Raises ServiceError on DB failure.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        # Fetch only the password hash — nothing else needed
        cursor.execute(
            "SELECT password FROM users WHERE id = %s",
            (user_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise ServiceError("User not found")

        # Verify current password before accepting the new one.
        # Without this check, anyone with a stolen JWT could lock the
        # real user out by changing their password within the token's
        # 24-hour validity window.
        if not bcrypt.checkpw(current_password.encode("utf-8"), row[0].encode("utf-8")):
            raise ValidationError("Current password is incorrect")

        new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "UPDATE users SET password = %s WHERE id = %s",
            (new_hash, user_id)
        )
        conn.commit()

    except (ValidationError, ServiceError):
        raise
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during change_password: %s", e, exc_info=True)
        raise ServiceError("A server error occurred while changing password")
    except RuntimeError as e:
        logger.error("Connection error during change_password: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)
