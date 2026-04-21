"""Auth routes blueprint."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.services.auth_service import (
    AuthConflictError,
    AuthServiceError,
    authenticate_user,
    register_user,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.get("/")
def index():
    """Render auth page with login/registration forms."""

    return render_template("auth/index.html")


@auth_bp.post("/login")
def login():
    """Authenticate a returning user and start a session."""

    try:
        user = authenticate_user(
            email=request.form.get("email"),
            password=request.form.get("password"),
        )
    except AuthServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.index"))

    _set_user_session(user)
    flash(f"Welcome back, {user['first_name']}.", "success")
    return redirect(url_for("dashboard.index"))


@auth_bp.post("/register")
def register():
    """Register a new user and start a session."""

    try:
        user = register_user(request.form.to_dict(flat=True))
    except AuthConflictError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.index"))
    except AuthServiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.index"))

    _set_user_session(user)
    flash("Account created successfully.", "success")
    return redirect(url_for("dashboard.index"))


@auth_bp.post("/logout")
def logout():
    """Clear the current session."""

    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.index"))


def _set_user_session(user: dict[str, object]) -> None:
    """Persist authenticated user data in session."""

    session["user_id"] = int(user["user_id"])
    session["user_email"] = str(user["email"])
    session["user_name"] = f"{user['first_name']} {user['last_name']}".strip()
