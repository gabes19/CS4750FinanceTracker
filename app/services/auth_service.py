"""Authentication service functions."""

from __future__ import annotations

from typing import Any

import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash

from app.db.connection import get_mysql_connection


class AuthServiceError(Exception):
    """Base auth exception."""


class AuthValidationError(AuthServiceError):
    """Raised when auth payload is invalid or credentials fail."""


class AuthConflictError(AuthServiceError):
    """Raised when trying to create a user that already exists."""


def authenticate_user(email: str | None, password: str | None) -> dict[str, Any]:
    """Return authenticated user row, or raise AuthValidationError."""

    normalized_email = _normalize_email(email)
    normalized_password = _normalize_password(password)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT user_id, email, password_hash, first_name, last_name
            FROM `user`
            WHERE LOWER(email) = LOWER(%s)
            LIMIT 1
            """,
            (normalized_email,),
        )
        user = cursor.fetchone()
        if user is None or not check_password_hash(user["password_hash"], normalized_password):
            raise AuthValidationError("Invalid email or password.")

        return {
            "user_id": int(user["user_id"]),
            "email": str(user["email"]),
            "first_name": str(user["first_name"]),
            "last_name": str(user["last_name"]),
        }
    finally:
        cursor.close()
        conn.close()


def register_user(payload: dict[str, Any]) -> dict[str, Any]:
    """Register and return a new user."""

    email = _normalize_email(payload.get("email"))
    password = _normalize_password(payload.get("password"))
    first_name = _normalize_name(payload.get("first_name"), field_name="first name")
    last_name = _normalize_name(payload.get("last_name"), field_name="last name")

    if len(password) < 8:
        raise AuthValidationError("Password must be at least 8 characters.")

    password_hash = generate_password_hash(password)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT 1 FROM `user` WHERE LOWER(email) = LOWER(%s) LIMIT 1",
            (email,),
        )
        if cursor.fetchone() is not None:
            raise AuthConflictError("An account with this email already exists.")

        cursor.execute(
            """
            INSERT INTO `user` (email, password_hash, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            """,
            (email, password_hash, first_name, last_name),
        )
        user_id = int(cursor.lastrowid)

        default_account_name = f"{first_name} Checking"
        cursor.execute(
            """
            INSERT INTO account (account_name, account_type, currency_code, current_balance, is_active)
            VALUES (%s, 'checking', 'USD', 0.00, 1)
            """,
            (default_account_name,),
        )
        account_id = int(cursor.lastrowid)

        cursor.execute(
            """
            INSERT INTO owns (user_id, account_id, ownership_role)
            VALUES (%s, %s, 'owner')
            """,
            (user_id, account_id),
        )

        conn.commit()
        return {
            "user_id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }
    except mysql.connector.Error as exc:
        conn.rollback()
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise AuthValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def _normalize_email(raw_email: str | None) -> str:
    """Validate and normalize email."""

    value = (raw_email or "").strip().lower()
    if not value:
        raise AuthValidationError("Email is required.")
    if "@" not in value or "." not in value.split("@")[-1]:
        raise AuthValidationError("Enter a valid email address.")
    if len(value) > 255:
        raise AuthValidationError("Email is too long.")
    return value


def _normalize_password(raw_password: str | None) -> str:
    """Validate and normalize password input."""

    value = raw_password or ""
    if not value:
        raise AuthValidationError("Password is required.")
    if len(value) > 255:
        raise AuthValidationError("Password is too long.")
    return value


def _normalize_name(raw_value: str | None, *, field_name: str) -> str:
    """Validate and normalize display names."""

    value = (raw_value or "").strip()
    if not value:
        raise AuthValidationError(f"{field_name.title()} is required.")
    if len(value) > 100:
        raise AuthValidationError(f"{field_name.title()} is too long.")
    return value
