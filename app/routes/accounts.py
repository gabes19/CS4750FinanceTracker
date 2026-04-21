"""Accounts routes blueprint."""

from flask import Blueprint, render_template


accounts_bp = Blueprint("accounts", __name__, url_prefix="/accounts")


@accounts_bp.get("/")
def index():
    return render_template("accounts/index.html")
