from flask import Blueprint, request, jsonify, g
import logging
from middleware.auth_middleware import token_required, admin_required
from services.order_service import (
    validate_checkout_input, place_order,
    get_user_orders, get_user_order_history, get_order_by_id,
    update_order_status, get_admin_orders, get_admin_order_detail,
    VALID_STATUSES,
)
from services.db_utils import (
    ServiceError, ValidationError, NotFoundError,
    ForbiddenError, InsufficientStockError,
    parse_pagination,
)

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")
logger = logging.getLogger(__name__)


@orders_bp.route("/checkout", methods=["POST"])
@token_required
def checkout():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        items = validate_checkout_input(data)
        order = place_order(int(g.current_user["id"]), items)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except InsufficientStockError as e:
        return jsonify({"error": str(e)}), 409
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error in /orders/checkout: %s", e)
        return jsonify({"error": "Checkout failed due to an unexpected server error"}), 500

    return jsonify({"message": "Order placed successfully", "order": order}), 201


@orders_bp.route("", methods=["GET"])
@token_required
def list_orders():
    try:
        orders = get_user_orders(int(g.current_user["id"]))
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"orders": orders}), 200


@orders_bp.route("/my-orders", methods=["GET"])
@token_required
def list_my_orders():
    try:
        orders = get_user_order_history(int(g.current_user["id"]))
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error in /orders/my-orders: %s", e)
        return jsonify({"error": "Failed to load order history due to an unexpected server error"}), 500

    return jsonify({"orders": orders}), 200


@orders_bp.route("/<int:order_id>", methods=["GET"])
@token_required
def retrieve_order(order_id):
    try:
        order = get_order_by_id(
            order_id,
            requesting_user_id=int(g.current_user["id"]),
            is_admin=g.current_user.get("role") == "admin",
        )
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ForbiddenError as e:
        return jsonify({"error": str(e)}), 403
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"order": order}), 200


@orders_bp.route("/<int:order_id>/status", methods=["PATCH"])
@admin_required
def change_order_status(order_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    if "status" not in data:
        return jsonify({"error": "status is required"}), 400

    try:
        order, new_status = update_order_status(order_id, data)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "message": f"Order status updated to {new_status}",
        "order":   order,
    }), 200


@orders_bp.route("/admin/orders", methods=["GET"])
@admin_required
def admin_list_orders():
    page, limit, err = parse_pagination(request.args)
    if err:
        return jsonify({"error": err}), 400

    status_filter = request.args.get("status", "").strip().upper() or None
    if status_filter and status_filter not in VALID_STATUSES:
        return jsonify({
            "error": f"Invalid status filter. Allowed: {', '.join(sorted(VALID_STATUSES))}"
        }), 400

    sort_raw = request.args.get("sort", "desc").strip().lower()
    sort_dir = "ASC" if sort_raw == "asc" else "DESC"

    try:
        orders, total = get_admin_orders(page, limit, status_filter, sort_dir)
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "orders": orders,
        "pagination": {
            "page":        page,
            "limit":       limit,
            "total":       total,
            "total_pages": -(-total // limit),
        }
    }), 200


@orders_bp.route("/admin/orders/<int:order_id>", methods=["GET"])
@admin_required
def admin_retrieve_order(order_id):
    try:
        order = get_admin_order_detail(order_id)
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"order": order}), 200
