"""Transactions routes blueprint."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.transaction_service import (
    TransactionFilters,
    TransactionForbiddenError,
    TransactionNotFoundError,
    TransactionServiceError,
    TransactionValidationError,
    create_transaction,
    delete_transaction,
    list_user_accounts,
    list_user_categories,
    list_user_transactions,
    update_transaction,
)


transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@transactions_bp.get("/")
def index():
    """Render transactions page with initial user-scoped data."""

    user_id = _session_user_id_or_none()
    if user_id is None:
        return redirect(url_for("auth.index"))

    filters = _build_filters_from_args(request.args)
    transactions = list_user_transactions(user_id, filters)
    accounts = list_user_accounts(user_id)
    categories = list_user_categories(user_id)

    return render_template(
        "transactions/transactions.html",
        transactions=transactions,
        accounts=accounts,
        categories=categories,
        filters=filters,
    )


@transactions_bp.get("/api")
def list_transactions_api():
    """Return filtered transactions for the logged-in user."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    filters = _build_filters_from_args(request.args)
    transactions = list_user_transactions(user_id, filters)

    return jsonify(
        {
            "transactions": transactions,
            "filters": {
                "start_date": filters.start_date,
                "end_date": filters.end_date,
                "category_id": filters.category_id,
                "account_id": filters.account_id,
                "keyword": filters.keyword,
                "sort_by": filters.sort_by,
                "sort_dir": filters.sort_dir,
            },
        }
    )


@transactions_bp.post("/api")
def create_transaction_api():
    """Create a user-scoped transaction."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    payload = _request_payload()

    try:
        transaction = create_transaction(user_id, payload)
        return jsonify({"message": "Transaction created.", "transaction": transaction}), 201
    except TransactionServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@transactions_bp.put("/api/<int:transaction_id>")
def update_transaction_api(transaction_id: int):
    """Update a user-scoped transaction."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    payload = _request_payload()

    try:
        transaction = update_transaction(user_id, transaction_id, payload)
        return jsonify({"message": "Transaction updated.", "transaction": transaction})
    except TransactionServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@transactions_bp.delete("/api/<int:transaction_id>")
def delete_transaction_api(transaction_id: int):
    """Delete a user-scoped transaction."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    try:
        delete_transaction(user_id, transaction_id)
        return jsonify({"message": "Transaction deleted.", "transaction_id": transaction_id})
    except TransactionServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@transactions_bp.errorhandler(TransactionValidationError)
def _handle_validation_error(exc: TransactionValidationError):
    return jsonify({"error": str(exc)}), 400


@transactions_bp.errorhandler(TransactionNotFoundError)
def _handle_not_found_error(exc: TransactionNotFoundError):
    return jsonify({"error": str(exc)}), 404


@transactions_bp.errorhandler(TransactionForbiddenError)
def _handle_forbidden_error(exc: TransactionForbiddenError):
    return jsonify({"error": str(exc)}), 403


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


def _build_filters_from_args(args) -> TransactionFilters:
    """Convert request args to a strongly-typed filter object."""

    def _as_optional_int(value: str | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None

    sort_by = (args.get("sort_by") or "date").lower()
    if sort_by not in {"date", "amount"}:
        sort_by = "date"

    sort_dir = (args.get("sort_dir") or "desc").lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    return TransactionFilters(
        start_date=args.get("start_date") or None,
        end_date=args.get("end_date") or None,
        category_id=_as_optional_int(args.get("category_id")),
        account_id=_as_optional_int(args.get("account_id")),
        keyword=(args.get("keyword") or "").strip() or None,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
