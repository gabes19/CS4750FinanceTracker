"""Budgets routes blueprint."""

from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.budget_service import (
    BudgetFilters,
    BudgetForbiddenError,
    BudgetNotFoundError,
    BudgetServiceError,
    BudgetValidationError,
    create_budget,
    delete_budget,
    list_user_budgets,
    list_user_categories,
    update_budget,
)


budgets_bp = Blueprint("budgets", __name__, url_prefix="/budgets")


@budgets_bp.get("/")
def index():
    """Render budget management page."""

    user_id = _session_user_id_or_none()
    if user_id is None:
        return redirect(url_for("auth.index"))

    selected_month = request.args.get("month") or date.today().strftime("%Y-%m")
    filters = BudgetFilters(month=selected_month)

    try:
        budgets = list_user_budgets(user_id, filters)
    except BudgetValidationError:
        filters = BudgetFilters(month=date.today().strftime("%Y-%m"))
        budgets = list_user_budgets(user_id, filters)

    categories = list_user_categories(user_id)

    return render_template(
        "budgets/budgets.html",
        budgets=budgets,
        categories=categories,
        filters=filters,
    )


@budgets_bp.get("/api")
def list_budgets_api():
    """Return user-scoped budgets as JSON."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    month = request.args.get("month") or date.today().strftime("%Y-%m")

    try:
        budgets = list_user_budgets(user_id, BudgetFilters(month=month))
    except BudgetValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "budgets": budgets,
            "month": month,
        }
    )


@budgets_bp.post("/api")
def create_budget_api():
    """Create a user-scoped budget."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    payload = _request_payload()

    try:
        budget = create_budget(user_id, payload)
        return jsonify({"message": "Budget created.", "budget": budget}), 201
    except BudgetServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@budgets_bp.put("/api/<int:budget_id>")
def update_budget_api(budget_id: int):
    """Update a user-scoped budget."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    payload = _request_payload()

    try:
        budget = update_budget(user_id, budget_id, payload)
        return jsonify({"message": "Budget updated.", "budget": budget})
    except BudgetServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@budgets_bp.delete("/api/<int:budget_id>")
def delete_budget_api(budget_id: int):
    """Delete a user-scoped budget."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    try:
        delete_budget(user_id, budget_id)
        return jsonify({"message": "Budget deleted.", "budget_id": budget_id})
    except BudgetServiceError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@budgets_bp.errorhandler(BudgetValidationError)
def _handle_validation_error(exc: BudgetValidationError):
    return jsonify({"error": str(exc)}), 400


@budgets_bp.errorhandler(BudgetNotFoundError)
def _handle_not_found_error(exc: BudgetNotFoundError):
    return jsonify({"error": str(exc)}), 404


@budgets_bp.errorhandler(BudgetForbiddenError)
def _handle_forbidden_error(exc: BudgetForbiddenError):
    return jsonify({"error": str(exc)}), 403


def _request_payload() -> dict[str, Any]:
    """Return payload from JSON request body or HTML form body."""

    json_payload = request.get_json(silent=True)
    if json_payload is not None:
        return json_payload

    form_payload = request.form.to_dict(flat=True)
    if "category_ids" in request.form:
        form_payload["category_ids"] = request.form.getlist("category_ids")
    return form_payload


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
    """Return user ID or JSON 401 response tuple."""

    user_id = _session_user_id_or_none()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401
    return user_id
