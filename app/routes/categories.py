"""Categories routes blueprint."""

from flask import Blueprint, render_template


categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


@categories_bp.get("/")
def index():
    return render_template("categories/index.html")
