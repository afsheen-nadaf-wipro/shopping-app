from functools import wraps
import jwt
from flask import request, jsonify, g
from config import JWT_SECRET


def _decode_token():
    """
    Extract and decode the Bearer token from the Authorization header.
    Returns (payload, None) on success or (None, response) on failure.
    Centralised here so both decorators share identical decode logic —
    a fix in one place covers both.
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Authorization header missing or malformed"}), 401)

    token = auth_header.split(" ", 1)[1].strip()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, (jsonify({"error": "Token has expired"}), 401)
    except jwt.InvalidTokenError:
        return None, (jsonify({"error": "Invalid token"}), 401)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err = _decode_token()
        if err:
            return err

        g.current_user = {
            "id":    payload["sub"],
            "email": payload["email"],
            "role":  payload["role"],
        }
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err = _decode_token()
        if err:
            return err

        if payload.get("role") != "admin":
            return jsonify({"error": "Access forbidden: admins only"}), 403

        g.current_user = {
            "id":    payload["sub"],
            "email": payload["email"],
            "role":  payload["role"],
        }
        return f(*args, **kwargs)
    return decorated
