"""Accounts routes blueprint."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.accounts_service import (
    AccountServiceError,
    add_funds_to_account,
    list_user_accounts_with_balance,
)


accounts_bp = Blueprint("accounts", __name__, url_prefix="/accounts")


@accounts_bp.get("/")
def index():
    """Render accounts page with user-scoped account balances."""

    user_id = _session_user_id_or_none()
    if user_id is None:
        return redirect(url_for("auth.index"))

    accounts = list_user_accounts_with_balance(user_id)
    return render_template("accounts/index.html", accounts=accounts)


@accounts_bp.get("/api")
def list_accounts_api():
    """Return all visible user accounts with current balances."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    accounts = list_user_accounts_with_balance(user_id)
    return jsonify({"accounts": accounts})


@accounts_bp.post("/api/add-funds")
def add_funds_api():
    """Increase account balance for an owner account."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    payload = _request_payload()
    try:
        account = add_funds_to_account(user_id, payload)
        return jsonify({"message": "Funds added.", "account": account})
    except AccountServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


def _request_payload() -> dict[str, Any]:
    """Return payload from JSON request body or HTML form body."""

    return request.get_json(silent=True) or request.form.to_dict(flat=True)


def _session_user_id_or_none() -> int | None:
    """Read user ID from session if present and valid."""

    raw = session.get("user_id")
    if raw is None:
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _require_session_user_id_json() -> int | tuple[Any, int]:
    """Return user ID or a JSON 401 response tuple if missing."""

    user_id = _session_user_id_or_none()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401
    return user_id
