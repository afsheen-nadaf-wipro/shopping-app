"""
services/order_service.py

Business logic and DB operations for the orders domain.
No Flask imports — raises service exceptions, returns plain Python dicts.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
import psycopg2

from db import get_connection
from services.db_utils import (
    close, ServiceError, ValidationError, NotFoundError,
    ForbiddenError, InsufficientStockError,
    PAGINATION_MAX_LIMIT, PAGINATION_DEFAULT_LIMIT,
)

logger = logging.getLogger(__name__)


def _to_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_STATUSES = {"PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"}

VALID_TRANSITIONS = {
    "PENDING":    {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"SHIPPED",    "CANCELLED"},
    "SHIPPED":    {"DELIVERED"},
    "DELIVERED":  set(),
    "CANCELLED":  set(),
}


# ── Serializers ───────────────────────────────────────────────────────────────

def _serialize_order(row):
    return {
        "id":           row[0],
        "user_id":      row[1],
        "total_amount": round(float(row[2]), 2),
        "status":       row[3],
        "created_at":   _to_iso(row[4]),
    }


def _serialize_item(row):
    price    = round(float(row[3]), 2)
    quantity = row[2]
    return {
        "id":         row[0],
        "product_id": row[1],
        "quantity":   quantity,
        "price":      price,
        "subtotal":   round(price * quantity, 2),
    }


def _serialize_admin_order(row):
    return {
        "id":             row[0],
        "customer_id":    row[1],
        "customer_email": row[2],
        "total_amount":   round(float(row[3]), 2),
        "status":         row[4],
        "created_at":     _to_iso(row[5]),
    }


# ── Validation ────────────────────────────────────────────────────────────────

def validate_checkout_input(data):
    """
    Validates and normalises the checkout payload.
    Duplicate product IDs are merged by summing quantities.
    Returns a list of {product_id, quantity} dicts or raises ValidationError.
    """
    items = data.get("items")

    if not isinstance(items, list):
        raise ValidationError("'items' must be a list")
    if len(items) == 0:
        raise ValidationError("'items' cannot be empty")

    merged = {}

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(f"item at index {i} must be an object")

        if "product_id" not in item:
            raise ValidationError(f"item at index {i} is missing 'product_id'")
        try:
            product_id = int(item["product_id"])
            if product_id <= 0:
                raise ValidationError(
                    f"item at index {i}: 'product_id' must be a positive integer"
                )
        except (ValueError, TypeError):
            raise ValidationError(
                f"item at index {i}: 'product_id' must be a valid integer"
            )

        if "quantity" not in item:
            raise ValidationError(f"item at index {i} is missing 'quantity'")
        raw_qty = item["quantity"]
        if isinstance(raw_qty, float) and not raw_qty.is_integer():
            raise ValidationError(
                f"item at index {i}: 'quantity' must be a whole number"
            )
        try:
            quantity = int(raw_qty)
        except (ValueError, TypeError):
            raise ValidationError(
                f"item at index {i}: 'quantity' must be a valid integer"
            )
        if quantity <= 0:
            raise ValidationError(
                f"item at index {i}: 'quantity' must be greater than 0"
            )

        merged[product_id] = merged.get(product_id, 0) + quantity

    return [{"product_id": pid, "quantity": qty} for pid, qty in merged.items()]


def validate_status_transition(data, current_status):
    """
    Validates a status update request against the transition graph.
    Returns new_status string or raises ValidationError.
    """
    if "status" not in data:
        raise ValidationError("status is required")

    new_status = (data["status"] or "").strip().upper()

    if new_status not in VALID_STATUSES:
        raise ValidationError(
            f"Invalid status '{new_status}'. "
            f"Allowed values: {', '.join(sorted(VALID_STATUSES))}"
        )

    allowed = VALID_TRANSITIONS.get(current_status, set())

    if not allowed:
        raise ValidationError(
            f"Order is '{current_status}' and cannot be modified. "
            "This is a terminal status."
        )

    if new_status not in allowed:
        raise ValidationError(
            f"Cannot transition from '{current_status}' to '{new_status}'. "
            f"Allowed transitions: {', '.join(sorted(allowed))}"
        )

    return new_status


# ── Service functions ─────────────────────────────────────────────────────────

def place_order(user_id, items):
    """
    Full checkout transaction:
      1. Lock each product row (FOR UPDATE — prevents race conditions)
      2. Validate stock for every item
      3. Insert order + order_items
      4. Decrement stock
      5. Commit

    Returns the created order dict or raises NotFoundError /
    InsufficientStockError / ServiceError.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        total_amount   = Decimal("0.00")
        enriched_items = []

        for item in items:
            product_id = item["product_id"]
            quantity   = item["quantity"]

            cursor.execute(
                "SELECT id, name, stock, price FROM products WHERE id = %s FOR UPDATE",
                (product_id,)
            )
            product = cursor.fetchone()

            if not product:
                conn.rollback()
                raise NotFoundError(f"Product with id {product_id} does not exist")

            _, name, stock, price = product

            if stock < quantity:
                conn.rollback()
                raise InsufficientStockError(
                    f"Insufficient stock for '{name}'. "
                    f"Available: {stock}, Requested: {quantity}"
                )

            total_amount += Decimal(str(price)) * quantity
            enriched_items.append({
                "product_id": product_id,
                "quantity":   quantity,
                "price":      price,
            })

        total_rounded = float(
            total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )

        cursor.execute(
            """
            INSERT INTO orders (user_id, total_amount, status)
            VALUES (%s, %s, 'PENDING')
            RETURNING id, user_id, total_amount, status, created_at
            """,
            (user_id, total_rounded)
        )
        order    = cursor.fetchone()
        order_id = order[0]

        for item in enriched_items:
            cursor.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (%s, %s, %s, %s)
                """,
                (order_id, item["product_id"], item["quantity"], item["price"])
            )
            cursor.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s",
                (item["quantity"], item["product_id"])
            )

        conn.commit()

    except (NotFoundError, InsufficientStockError):
        raise
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during place_order: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during checkout")
    except RuntimeError as e:
        if conn:
            conn.rollback()
        logger.error("Connection error during place_order: %s", e)
        raise ServiceError("Could not connect to the database")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Unexpected error during place_order: %s", e, exc_info=True)
        raise ServiceError("Checkout failed due to an unexpected error")
    finally:
        close(conn, cursor)

    return {
        "id":           order[0],
        "user_id":      order[1],
        "total_amount": round(float(order[2]), 2),
        "status":       order[3],
        "created_at":   _to_iso(order[4]),
        "items": [
            {
                "product_id": i["product_id"],
                "quantity":   i["quantity"],
                "price":      round(float(i["price"]), 2),
                "subtotal":   round(float(i["price"]) * i["quantity"], 2),
            }
            for i in enriched_items
        ],
    }


def get_user_orders(user_id):
    """Returns list of orders for a user or raises ServiceError."""
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, total_amount, status, created_at
            FROM orders WHERE user_id = %s ORDER BY created_at DESC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
    except psycopg2.Error as e:
        logger.error("psycopg2 error during get_user_orders: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during fetching orders")
    except RuntimeError as e:
        logger.error("Connection error during get_user_orders: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return [_serialize_order(r) for r in rows]


def get_user_order_history(user_id):
    """
    Returns all orders for a user with nested purchased items.
    Results are sorted newest first and include order history fields
    tailored for the customer-facing history page.
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                o.id,
                o.total_amount,
                o.status,
                o.created_at,
                p.name,
                oi.quantity,
                oi.price
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE o.user_id = %s
            ORDER BY o.created_at DESC, o.id DESC, oi.id ASC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
    except psycopg2.Error as e:
        logger.error(
            "psycopg2 error during get_user_order_history: %s",
            e,
            exc_info=True,
        )
        raise ServiceError("A server error occurred during fetching order history")
    except RuntimeError as e:
        logger.error("Connection error during get_user_order_history: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    orders = []
    orders_by_id = {}

    for row in rows:
        order_id = row[0]
        order = orders_by_id.get(order_id)
        if order is None:
            order = {
                "order_id": order_id,
                "total_amount": round(float(row[1]), 2),
                "status": row[2],
                "created_at": _to_iso(row[3]),
                "items": [],
            }
            orders_by_id[order_id] = order
            orders.append(order)

        if row[4] is not None:
            order["items"].append(
                {
                    "product_name": row[4],
                    "quantity": row[5],
                    "price_at_purchase": round(float(row[6]), 2),
                }
            )

    return orders


def get_order_by_id(order_id, requesting_user_id, is_admin):
    """
    Returns a single order with its items.
    Enforces ownership — non-admins can only see their own orders.
    Raises NotFoundError, ForbiddenError, or ServiceError.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, user_id, total_amount, status, created_at "
            "FROM orders WHERE id = %s",
            (order_id,)
        )
        order = cursor.fetchone()

        if not order:
            raise NotFoundError("Order not found")

        if not is_admin and order[1] != requesting_user_id:
            raise ForbiddenError("Access forbidden")

        cursor.execute(
            "SELECT id, product_id, quantity, price "
            "FROM order_items WHERE order_id = %s",
            (order_id,)
        )
        items = cursor.fetchall()

    except (NotFoundError, ForbiddenError):
        raise
    except psycopg2.Error as e:
        logger.error("psycopg2 error during get_order_by_id: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during fetching order")
    except RuntimeError as e:
        logger.error("Connection error during get_order_by_id: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return {**_serialize_order(order), "items": [_serialize_item(i) for i in items]}


def update_order_status(order_id, data):
    """
    Validates and applies a status transition.
    Uses FOR UPDATE to prevent concurrent admin updates from racing.
    Returns updated order dict or raises ValidationError / NotFoundError / ServiceError.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, status FROM orders WHERE id = %s FOR UPDATE",
            (order_id,)
        )
        order = cursor.fetchone()

        if not order:
            raise NotFoundError("Order not found")

        new_status = validate_status_transition(data, order[1])

        cursor.execute(
            """
            UPDATE orders SET status = %s WHERE id = %s
            RETURNING id, user_id, total_amount, status, created_at
            """,
            (new_status, order_id)
        )
        updated = cursor.fetchone()
        conn.commit()

    except (NotFoundError, ValidationError):
        raise
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during update_order_status: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during updating order status")
    except RuntimeError as e:
        if conn:
            conn.rollback()
        logger.error("Connection error during update_order_status: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return _serialize_order(updated), new_status


def get_admin_orders(page, limit, status_filter, sort_dir):
    """
    Returns paginated order list with customer info for admin view.
    sort_dir must already be validated to 'ASC' or 'DESC' by the caller.
    """
    offset = (page - 1) * limit
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        if status_filter:
            cursor.execute(
                f"""
                SELECT o.id, o.user_id, u.email, o.total_amount, o.status, o.created_at
                FROM orders o JOIN users u ON u.id = o.user_id
                WHERE o.status = %s
                ORDER BY o.created_at {sort_dir}
                LIMIT %s OFFSET %s
                """,
                (status_filter, limit, offset)
            )
        else:
            cursor.execute(
                f"""
                SELECT o.id, o.user_id, u.email, o.total_amount, o.status, o.created_at
                FROM orders o JOIN users u ON u.id = o.user_id
                ORDER BY o.created_at {sort_dir}
                LIMIT %s OFFSET %s
                """,
                (limit, offset)
            )

        rows = cursor.fetchall()

        if status_filter:
            cursor.execute(
                "SELECT COUNT(*) FROM orders WHERE status = %s", (status_filter,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM orders")

        total = cursor.fetchone()[0]

    except psycopg2.Error as e:
        logger.error("psycopg2 error during get_admin_orders: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during fetching admin orders")
    except RuntimeError as e:
        logger.error("Connection error during get_admin_orders: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return [_serialize_admin_order(r) for r in rows], total


def get_admin_order_detail(order_id):
    """Returns full order detail with customer and product info for admin view."""
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT o.id, o.user_id, u.name, u.email, o.total_amount, o.status, o.created_at
            FROM orders o JOIN users u ON u.id = o.user_id
            WHERE o.id = %s
            """,
            (order_id,)
        )
        order = cursor.fetchone()

        if not order:
            raise NotFoundError("Order not found")

        cursor.execute(
            """
            SELECT oi.id, oi.product_id, p.name, oi.quantity, oi.price
            FROM order_items oi JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id = %s
            """,
            (order_id,)
        )
        items = cursor.fetchall()

    except NotFoundError:
        raise
    except psycopg2.Error as e:
        logger.error("psycopg2 error during get_admin_order_detail: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during fetching admin order detail")
    except RuntimeError as e:
        logger.error("Connection error during get_admin_order_detail: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return {
        "id":           order[0],
        "status":       order[5],
        "total_amount": round(float(order[4]), 2),
        "created_at":   _to_iso(order[6]),
        "customer": {
            "id":    order[1],
            "name":  order[2],
            "email": order[3],
        },
        "items": [
            {
                "id":           row[0],
                "product_id":   row[1],
                "product_name": row[2],
                "quantity":     row[3],
                "price":        round(float(row[4]), 2),
                "subtotal":     round(float(row[4]) * row[3], 2),
            }
            for row in items
        ],
    }
