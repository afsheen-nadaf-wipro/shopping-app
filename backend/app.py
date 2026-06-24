import logging
import os
from flask import Flask
from flask_cors import CORS
from routes.auth import auth_bp
from routes.products import products_bp
from routes.orders import orders_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = Flask(__name__)


def _allowed_origins() -> list[str] | str:
    """Return a normalized allowlist for Flask-CORS.

    Supports ALLOWED_ORIGINS as:
    - single origin: https://example.com
    - comma-separated origins: https://a.com,https://b.com
    - wildcard: *
    """
    raw = os.getenv("ALLOWED_ORIGINS", "https://shopping-app-orcin-rho.vercel.app").strip()
    if raw == "*":
        return "*"

    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["https://shopping-app-orcin-rho.vercel.app"]


CORS(
    app,
    resources={r"/*": {"origins": _allowed_origins()}},
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.register_blueprint(auth_bp)
app.register_blueprint(products_bp)
app.register_blueprint(orders_bp)


@app.route("/")
def home():
    return {"message": "Shopping App Backend Running"}


if __name__ == "__main__":
    # debug=True is only active when APP_ENV=development is set explicitly.
    # In production (gunicorn/uwsgi) this block is never executed at all.
    debug = os.getenv("APP_ENV", "production") == "development"
    app.run(debug=debug)
