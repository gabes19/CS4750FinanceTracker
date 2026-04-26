"""Account service functions for balance display and funding operations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import mysql.connector

from app.db.connection import get_mysql_connection


class AccountServiceError(Exception):
    """Base account service exception."""

    status_code = 400


class AccountValidationError(AccountServiceError):
    """Raised when account request payload is invalid."""

    status_code = 400


class AccountNotFoundError(AccountServiceError):
    """Raised when account cannot be found for the user."""

    status_code = 404


class AccountForbiddenError(AccountServiceError):
    """Raised when user is not allowed to mutate target account."""

    status_code = 403


def list_user_accounts_with_balance(user_id: int) -> list[dict[str, Any]]:
    """Return accounts visible to a user ordered by account name."""

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
              a.account_id,
              a.account_name,
              a.account_type,
              a.currency_code,
              a.current_balance,
              a.is_active,
              o.ownership_role
            FROM owns o
            INNER JOIN account a ON a.account_id = o.account_id
            WHERE o.user_id = %s
            ORDER BY a.account_name ASC
            """,
            (user_id,),
        )

        rows = cursor.fetchall()
        return [
            {
                "account_id": int(row["account_id"]),
                "account_name": str(row["account_name"]),
                "account_type": str(row["account_type"]),
                "currency_code": str(row["currency_code"]),
                "current_balance": float(Decimal(row["current_balance"])),
                "is_active": bool(row["is_active"]),
                "ownership_role": str(row["ownership_role"]),
            }
            for row in rows
        ]
    finally:
        cursor.close()
        conn.close()


def add_funds_to_account(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Add funds to an owned account and return updated row."""

    account_id = _normalize_account_id(payload.get("account_id"))
    amount = _normalize_amount(payload.get("amount"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT o.ownership_role
            FROM owns o
            WHERE o.user_id = %s AND o.account_id = %s
            LIMIT 1
            """,
            (user_id, account_id),
        )
        ownership = cursor.fetchone()
        if ownership is None:
            _raise_for_missing_or_forbidden(cursor, user_id=user_id, account_id=account_id)

        if ownership["ownership_role"] != "owner":
            raise AccountForbiddenError("Only account owners can add funds.")

        cursor.execute(
            """
            UPDATE account
            SET current_balance = current_balance + %s
            WHERE account_id = %s
            """,
            (amount, account_id),
        )
        if cursor.rowcount != 1:
            raise AccountNotFoundError("Account not found.")

        conn.commit()
        return _get_account_for_user(cursor, user_id=user_id, account_id=account_id)
    except AccountServiceError:
        conn.rollback()
        raise
    except mysql.connector.Error as exc:
        conn.rollback()
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise AccountValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def _get_account_for_user(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    account_id: int,
) -> dict[str, Any]:
    """Fetch one account row scoped to a user."""

    cursor.execute(
        """
        SELECT
          a.account_id,
          a.account_name,
          a.account_type,
          a.currency_code,
          a.current_balance,
          a.is_active,
          o.ownership_role
        FROM owns o
        INNER JOIN account a ON a.account_id = o.account_id
        WHERE o.user_id = %s
          AND a.account_id = %s
        LIMIT 1
        """,
        (user_id, account_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise AccountNotFoundError("Account not found.")

    return {
        "account_id": int(row["account_id"]),
        "account_name": str(row["account_name"]),
        "account_type": str(row["account_type"]),
        "currency_code": str(row["currency_code"]),
        "current_balance": float(Decimal(row["current_balance"])),
        "is_active": bool(row["is_active"]),
        "ownership_role": str(row["ownership_role"]),
    }


def _raise_for_missing_or_forbidden(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    account_id: int,
) -> None:
    """Raise specific error based on account existence and user membership."""

    cursor.execute(
        "SELECT account_id FROM account WHERE account_id = %s LIMIT 1",
        (account_id,),
    )
    if cursor.fetchone() is None:
        raise AccountNotFoundError("Account not found.")

    cursor.execute(
        "SELECT 1 FROM owns WHERE user_id = %s AND account_id = %s LIMIT 1",
        (user_id, account_id),
    )
    if cursor.fetchone() is None:
        raise AccountForbiddenError("You do not have access to this account.")

    raise AccountNotFoundError("Account not found.")


def _normalize_account_id(raw_account_id: Any) -> int:
    """Validate and normalize account ID."""

    try:
        account_id = int(raw_account_id)
    except (TypeError, ValueError) as exc:
        raise AccountValidationError("account_id must be an integer.") from exc

    if account_id <= 0:
        raise AccountValidationError("account_id must be a positive integer.")

    return account_id


def _normalize_amount(raw_amount: Any) -> Decimal:
    """Validate and normalize amount to 2 decimal places."""

    try:
        amount = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AccountValidationError("amount must be a valid decimal number.") from exc

    if amount <= 0:
        raise AccountValidationError("amount must be greater than 0.")

    return amount
