from flask import Blueprint, request, jsonify
import logging
from middleware.auth_middleware import admin_required
from services.product_service import (
    parse_product_filters, get_products, get_product_by_id,
    validate_create_input, create_product,
    validate_update_input, update_product,
    delete_product,
)
from services.db_utils import ServiceError, ValidationError, NotFoundError

products_bp = Blueprint("products", __name__, url_prefix="/products")
logger = logging.getLogger(__name__)


@products_bp.route("", methods=["GET"])
def list_products():
    try:
        filters          = parse_product_filters(request.args)
        products, total  = get_products(filters)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error in GET /products: %s", e)
        return jsonify({"error": "Failed to load products due to an unexpected server error"}), 500

    limit = filters["limit"]
    return jsonify({
        "products": products,
        "pagination": {
            "page":          filters["page"],
            "limit":         limit,
            "total_records": total,
            "total_pages":   -(-total // limit),
        }
    }), 200


@products_bp.route("/<int:product_id>", methods=["GET"])
def retrieve_product(product_id):
    try:
        product = get_product_by_id(product_id)
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"product": product}), 200


@products_bp.route("", methods=["POST"])
@admin_required
def add_product():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        fields  = validate_create_input(data)
        product = create_product(fields)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Product created", "product": product}), 201


@products_bp.route("/<int:product_id>", methods=["PUT"])
@admin_required
def edit_product(product_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        fields  = validate_update_input(data)
        product = update_product(product_id, fields)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "Product updated", "product": product}), 200


@products_bp.route("/<int:product_id>", methods=["DELETE"])
@admin_required
def remove_product(product_id):
    try:
        delete_product(product_id)
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": f"Product {product_id} deleted successfully"}), 200
