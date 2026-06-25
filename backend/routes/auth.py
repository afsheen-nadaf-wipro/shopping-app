from flask import Blueprint, request, jsonify, g
import logging
from middleware.auth_middleware import token_required
from services.auth_service import (
    validate_register_input, validate_login_input,
    validate_profile_update, validate_change_password,
    register_user, login_user,
    get_profile, update_profile, change_password,
)
from services.db_utils import (
    ServiceError, ValidationError, ConflictError, NotFoundError,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
logger = logging.getLogger(__name__)


# ── POST /auth/register ───────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        name, email, password = validate_register_input(data)
        user = register_user(name, email, password)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error in /auth/register: %s", e)
        return jsonify({"error": "Registration failed due to an unexpected server error"}), 500

    return jsonify({"message": "User registered successfully", "user": user}), 201


# ── POST /auth/login ──────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        email, password = validate_login_input(data)
        token, user     = login_user(email, password)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 401
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error in /auth/login: %s", e)
        return jsonify({"error": "Login failed due to an unexpected server error"}), 500

    return jsonify({"token": token, "user": user}), 200


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    return jsonify({"user": g.current_user}), 200


# ── GET /auth/profile ─────────────────────────────────────────────────────────

@auth_bp.route("/profile", methods=["GET"])
@token_required
def get_user_profile():
    # user_id always comes from the verified JWT — never from the request body
    try:
        profile = get_profile(int(g.current_user["id"]))
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"profile": profile}), 200


# ── PUT /auth/profile ─────────────────────────────────────────────────────────

@auth_bp.route("/profile", methods=["PUT"])
@token_required
def update_user_profile():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        fields  = validate_profile_update(data)
        profile = update_profile(int(g.current_user["id"]), fields)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Profile updated successfully", "profile": profile}), 200


# ── PUT /auth/change-password ─────────────────────────────────────────────────

@auth_bp.route("/change-password", methods=["PUT"])
@token_required
def change_user_password():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        current_pw, new_pw = validate_change_password(data)
        change_password(int(g.current_user["id"]), current_pw, new_pw)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Password changed successfully"}), 200
