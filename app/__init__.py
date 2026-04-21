"""Flask application factory."""

from __future__ import annotations

from flask import Flask

from config import get_config


def create_app(config_object: object | None = None) -> Flask:
    """Create and configure the Flask app instance."""

    app = Flask(__name__, template_folder="templates", static_folder="static")

    if config_object is None:
        app.config.from_object(get_config())
    elif isinstance(config_object, dict):
        app.config.from_mapping(config_object)
    else:
        app.config.from_object(config_object)

    register_blueprints(app)

    return app


def register_blueprints(app: Flask) -> None:
    """Register all route blueprints."""

    from app.routes.accounts import accounts_bp
    from app.routes.auth import auth_bp
    from app.routes.budgets import budgets_bp
    from app.routes.categories import categories_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.transactions import transactions_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(categories_bp)
