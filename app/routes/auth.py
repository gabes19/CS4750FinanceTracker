"""Auth routes blueprint."""

from flask import Blueprint, render_template


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.get("/")
def index():
    return render_template("auth/index.html")
