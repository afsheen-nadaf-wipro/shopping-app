"""
services/product_service.py

Business logic and DB operations for the products domain.
No Flask imports — all functions take plain Python arguments and return
plain Python dicts, or raise service exceptions.
"""
import re
import logging
import psycopg2

from db import get_connection
from services.db_utils import (
    close, ServiceError, ValidationError, NotFoundError,
    PAGINATION_MAX_LIMIT, PAGINATION_DEFAULT_LIMIT,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_UPDATE_FIELDS = {"name", "description", "price", "stock", "image_url"}

SORT_OPTIONS = {
    "price_asc":  "price ASC",
    "price_desc": "price DESC",
    "newest":     "created_at DESC",
    "oldest":     "created_at ASC",
    "name_asc":   "name ASC",
    "name_desc":  "name DESC",
}
DEFAULT_SORT = "newest"

_IMAGE_URL_RE = re.compile(r"^https?://.{1,490}$")


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(row):
    return {
        "id":          row[0],
        "name":        row[1],
        "description": row[2],
        "price":       round(float(row[3]), 2),
        "stock":       row[4],
        "image_url":   row[5],
        "created_at":  row[6].isoformat(),
    }


# ── Input validation ──────────────────────────────────────────────────────────

def _validate_image_url(value):
    url = (value or "").strip()
    if url and not _IMAGE_URL_RE.match(url):
        raise ValidationError(
            "image_url must start with http:// or https:// and be at most 500 characters"
        )
    return url


def validate_create_input(data):
    """Returns a clean fields dict or raises ValidationError."""
    name      = (data.get("name") or "").strip()
    price     = data.get("price")
    stock     = data.get("stock", 0)
    desc      = (data.get("description") or "").strip()
    image_url = _validate_image_url(data.get("image_url", ""))

    if not name:
        raise ValidationError("name is required")
    if len(name) > 200:
        raise ValidationError("name must be 200 characters or fewer")
    if price is None:
        raise ValidationError("price is required")

    try:
        price = round(float(price), 2)
        if price <= 0:
            raise ValidationError("price must be greater than 0")
    except (ValueError, TypeError):
        raise ValidationError("price must be a valid number")

    try:
        stock = int(stock)
        if stock < 0:
            raise ValidationError("stock must be a non-negative integer")
    except (ValueError, TypeError):
        raise ValidationError("stock must be a valid integer")

    return {"name": name, "description": desc, "price": price,
            "stock": stock, "image_url": image_url}


def validate_update_input(data):
    """
    Only fields explicitly present in the request are validated and returned.
    A missing field never appears in the result dict and never reaches the
    SET clause — preventing silent overwrites.
    """
    fields = {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise ValidationError("name cannot be empty")
        if len(name) > 200:
            raise ValidationError("name must be 200 characters or fewer")
        fields["name"] = name

    if "description" in data:
        fields["description"] = (data["description"] or "").strip()

    if "image_url" in data:
        fields["image_url"] = _validate_image_url(data["image_url"])

    if "price" in data:
        try:
            price = round(float(data["price"]), 2)
            if price <= 0:
                raise ValidationError("price must be greater than 0")
            fields["price"] = price
        except (ValueError, TypeError):
            raise ValidationError("price must be a valid number")

    if "stock" in data:
        try:
            stock = int(data["stock"])
            if stock < 0:
                raise ValidationError("stock must be a non-negative integer")
            fields["stock"] = stock
        except (ValueError, TypeError):
            raise ValidationError("stock must be a valid integer")

    if not fields:
        raise ValidationError("at least one field must be provided for update")

    return fields


def _build_set_clause(fields):
    """
    Builds a parameterised SET clause from a validated fields dict.
    Column names are checked against ALLOWED_UPDATE_FIELDS — no user string
    ever reaches the SQL text directly.
    """
    safe_cols = [col for col in fields if col in ALLOWED_UPDATE_FIELDS]
    if not safe_cols:
        raise ValidationError("no valid fields to update")
    set_clause = ", ".join(f"{col} = %s" for col in safe_cols)
    values     = [fields[col] for col in safe_cols]
    return set_clause, values


# ── Query builder for GET /products ──────────────────────────────────────────

def parse_product_filters(args):
    """
    Parses and validates all GET /products query parameters.
    Returns a filters dict or raises ValidationError.

    All user values go into a params list — none reach the SQL string directly.
    sort_key is used only as a dict key into SORT_OPTIONS; the SQL fragment
    that goes into the query comes from that dict (a Python literal), not from
    the user.
    """
    filters = {
        "conditions": [],
        "params":     [],
        "order_by":   SORT_OPTIONS[DEFAULT_SORT],
        "limit":      PAGINATION_DEFAULT_LIMIT,
        "offset":     0,
        "page":       1,
    }

    search = (args.get("search") or "").strip()
    if search:
        if len(search) > 100:
            raise ValidationError("search term must be 100 characters or fewer")
        filters["conditions"].append("(name ILIKE %s OR description ILIKE %s)")
        filters["params"].extend([f"%{search}%", f"%{search}%"])

    min_price = None
    if "min_price" in args:
        try:
            min_price = round(float(args["min_price"]), 2)
            if min_price < 0:
                raise ValidationError("min_price must be a non-negative number")
            filters["conditions"].append("price >= %s")
            filters["params"].append(min_price)
        except (ValueError, TypeError):
            raise ValidationError("min_price must be a valid number")

    max_price = None
    if "max_price" in args:
        try:
            max_price = round(float(args["max_price"]), 2)
            if max_price < 0:
                raise ValidationError("max_price must be a non-negative number")
            filters["conditions"].append("price <= %s")
            filters["params"].append(max_price)
        except (ValueError, TypeError):
            raise ValidationError("max_price must be a valid number")

    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValidationError("min_price cannot be greater than max_price")

    if "in_stock" in args:
        raw = args["in_stock"].strip().lower()
        if raw not in ("true", "false"):
            raise ValidationError("in_stock must be 'true' or 'false'")
        if raw == "true":
            filters["conditions"].append("stock > 0")

    sort_key = (args.get("sort") or DEFAULT_SORT).strip().lower()
    if sort_key not in SORT_OPTIONS:
        raise ValidationError(
            f"Invalid sort '{sort_key}'. Allowed: {', '.join(SORT_OPTIONS.keys())}"
        )
    filters["order_by"] = SORT_OPTIONS[sort_key]

    try:
        page = int(args.get("page", 1))
        if page < 1:
            raise ValidationError("page must be a positive integer")
        filters["page"] = page
    except (ValueError, TypeError):
        raise ValidationError("page must be a valid integer")

    try:
        limit = int(args.get("limit", PAGINATION_DEFAULT_LIMIT))
        if limit < 1:
            raise ValidationError("limit must be a positive integer")
        filters["limit"] = min(limit, PAGINATION_MAX_LIMIT)
    except (ValueError, TypeError):
        raise ValidationError("limit must be a valid integer")

    filters["offset"] = (filters["page"] - 1) * filters["limit"]
    return filters


def _build_product_query(filters):
    where = ""
    if filters["conditions"]:
        where = " WHERE " + " AND ".join(filters["conditions"])

    data_query = (
        f"SELECT id, name, description, price, stock, image_url, created_at "
        f"FROM products{where} "
        f"ORDER BY {filters['order_by']} "
        f"LIMIT %s OFFSET %s"
    )
    count_query  = f"SELECT COUNT(*) FROM products{where}"
    data_params  = filters["params"] + [filters["limit"], filters["offset"]]
    count_params = filters["params"]
    return data_query, data_params, count_query, count_params


# ── Service functions ─────────────────────────────────────────────────────────

def get_products(filters):
    """Returns (products_list, total_count) or raises ServiceError."""
    data_query, data_params, count_query, count_params = _build_product_query(filters)
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(data_query, data_params)
        rows = cursor.fetchall()
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]
    except psycopg2.Error as e:
        logger.error("psycopg2 error during get_products: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during fetching products")
    except RuntimeError as e:
        logger.error("Connection error during get_products: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return [_serialize(r) for r in rows], total


def get_product_by_id(product_id):
    """Returns a product dict or raises NotFoundError / ServiceError."""
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, price, stock, image_url, created_at "
            "FROM products WHERE id = %s",
            (product_id,)
        )
        row = cursor.fetchone()
    except psycopg2.Error as e:
        logger.error("psycopg2 error during get_product_by_id: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during fetching product")
    except RuntimeError as e:
        logger.error("Connection error during get_product_by_id: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    if not row:
        raise NotFoundError("Product not found")
    return _serialize(row)


def create_product(fields):
    """Inserts a new product and returns its dict, or raises ServiceError."""
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO products (name, description, price, stock, image_url)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, name, description, price, stock, image_url, created_at
            """,
            (fields["name"], fields["description"], fields["price"],
             fields["stock"], fields["image_url"])
        )
        row = cursor.fetchone()
        conn.commit()
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during create_product: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during creating product")
    except RuntimeError as e:
        logger.error("Connection error during create_product: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return _serialize(row)


def update_product(product_id, fields):
    """Updates a product and returns its dict, or raises NotFoundError / ServiceError."""
    set_clause, values = _build_set_clause(fields)
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            raise NotFoundError("Product not found")
        cursor.execute(
            f"UPDATE products SET {set_clause} WHERE id = %s "
            "RETURNING id, name, description, price, stock, image_url, created_at",
            values + [product_id]
        )
        row = cursor.fetchone()
        conn.commit()
    except NotFoundError:
        raise
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during update_product: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during updating product")
    except RuntimeError as e:
        logger.error("Connection error during update_product: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)

    return _serialize(row)


def delete_product(product_id):
    """Deletes a product or raises NotFoundError / ServiceError."""
    conn   = None
    cursor = None
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if not cursor.fetchone():
            raise NotFoundError("Product not found")
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
    except NotFoundError:
        raise
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error("psycopg2 error during delete_product: %s", e, exc_info=True)
        raise ServiceError("A server error occurred during deleting product")
    except RuntimeError as e:
        logger.error("Connection error during delete_product: %s", e)
        raise ServiceError("Could not connect to the database")
    finally:
        close(conn, cursor)
