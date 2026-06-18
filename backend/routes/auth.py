from flask import Blueprint, request, jsonify, g
import bcrypt
import re
import jwt
import datetime
from db import get_connection
from config import JWT_SECRET
from middleware.auth_middleware import token_required, admin_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def is_valid_email(email):
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$", email) is not None


def validate_register_input(data):
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return None, None, None, "name, email, and password are required"
    if not is_valid_email(email):
        return None, None, None, "Invalid email format"
    if len(password) < 6:
        return None, None, None, "Password must be at least 6 characters"

    return name, email, password, None


def validate_login_input(data):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return None, None, "email and password are required"
    if not is_valid_email(email):
        return None, None, "Invalid email format"

    return email, password, None


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    name, email, password, err = validate_register_input(data)
    if err:
        return jsonify({"error": err}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check for existing email
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Email already registered"}), 409

        # Hash password and insert user
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name, email, role, created_at
            """,
            (name, email, hashed_pw, "customer"),
        )
        user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "message": "User registered successfully",
        "user": {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "role": user[3],
            "created_at": user[4].isoformat(),
        }
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    email, password, err = validate_login_input(data)
    if err:
        return jsonify({"error": err}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, email, password, role FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    if not user or not bcrypt.checkpw(password.encode("utf-8"), user[3].encode("utf-8")):
        return jsonify({"error": "Invalid email or password"}), 401

    token = jwt.encode(
        {
            "sub": str(user[0]),
            "email": user[2],
            "role": user[4],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    return jsonify({
        "token": token,
        "user": {
            "id": user[0],
            "name": user[1],
            "role": user[4],
        }
    }), 200


@auth_bp.route("/debug-secret", methods=["GET"])
def debug_secret():
    return jsonify({"jwt_secret": JWT_SECRET}), 200


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    return jsonify({"user": g.current_user}), 200


@auth_bp.route("/admin-test", methods=["GET"])
@admin_required
def admin_test():
    return jsonify({"message": "Admin access granted"}), 200
