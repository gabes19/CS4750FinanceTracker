"""Dashboard routes blueprint."""

from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.dashboard_service import get_dashboard_snapshot


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/")


@dashboard_bp.get("/")
def index():
    """Render dashboard page with monthly summary and charts."""

    user_id = _session_user_id_or_none()
    if user_id is None:
        return redirect(url_for("auth.index"))

    selected_month = request.args.get("month") or date.today().strftime("%Y-%m")

    try:
        snapshot = get_dashboard_snapshot(user_id, selected_month)
    except ValueError:
        selected_month = date.today().strftime("%Y-%m")
        snapshot = get_dashboard_snapshot(user_id, selected_month)

    return render_template(
        "dashboard/dashboard.html",
        snapshot=snapshot,
        selected_month=selected_month,
    )


@dashboard_bp.get("/dashboard/api/summary")
def summary_api():
    """Return dashboard monthly aggregates for the logged-in user."""

    user_id = _require_session_user_id_json()
    if isinstance(user_id, tuple):
        return user_id

    selected_month = request.args.get("month") or date.today().strftime("%Y-%m")

    try:
        snapshot = get_dashboard_snapshot(user_id, selected_month)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(snapshot)


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
