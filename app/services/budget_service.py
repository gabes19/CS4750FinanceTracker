"""Budget service functions for user-scoped CRUD operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import mysql.connector

from app.db.connection import get_mysql_connection


class BudgetServiceError(Exception):
    """Base budget service exception."""

    status_code = 400


class BudgetValidationError(BudgetServiceError):
    """Raised when budget payload is invalid."""

    status_code = 400


class BudgetNotFoundError(BudgetServiceError):
    """Raised when budget cannot be found."""

    status_code = 404


class BudgetForbiddenError(BudgetServiceError):
    """Raised when user attempts unauthorized budget access."""

    status_code = 403


@dataclass
class BudgetFilters:
    """Optional budget filters for listing."""

    month: str | None = None


def list_user_categories(user_id: int) -> list[dict[str, Any]]:
    """Return categories available to this user (system + user-defined)."""

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT DISTINCT c.category_id, c.category_name, c.category_type
            FROM category c
            LEFT JOIN defines d ON d.category_id = c.category_id AND d.user_id = %s
            WHERE c.is_system_category = 1 OR d.user_id IS NOT NULL
            ORDER BY c.category_type ASC, c.category_name ASC
            """,
            (user_id,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def list_user_budgets(user_id: int, filters: BudgetFilters) -> list[dict[str, Any]]:
    """List budgets for a user with category mappings."""

    month_filter = _normalize_month(filters.month)

    params: list[Any] = [user_id]
    where_clauses = ["us.user_id = %s"]
    if month_filter is not None:
        where_clauses.append("b.budget_month = %s")
        params.append(month_filter)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            f"""
            SELECT
              b.budget_id,
              b.budget_name,
              b.budget_month,
              b.monthly_limit,
              c.category_id,
              c.category_name,
              c.category_type
            FROM user_sets us
            INNER JOIN budget b ON b.budget_id = us.budget_id
            LEFT JOIN applies_to ap ON ap.budget_id = b.budget_id
            LEFT JOIN category c ON c.category_id = ap.category_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY b.budget_month DESC, b.budget_id DESC, c.category_name ASC
            """,
            tuple(params),
        )
        rows = cursor.fetchall()
        return _group_budget_rows(rows)
    finally:
        cursor.close()
        conn.close()


def get_budget_by_id_for_user(user_id: int, budget_id: int) -> dict[str, Any]:
    """Get one budget for a specific user."""

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
              b.budget_id,
              b.budget_name,
              b.budget_month,
              b.monthly_limit,
              c.category_id,
              c.category_name,
              c.category_type
            FROM user_sets us
            INNER JOIN budget b ON b.budget_id = us.budget_id
            LEFT JOIN applies_to ap ON ap.budget_id = b.budget_id
            LEFT JOIN category c ON c.category_id = ap.category_id
            WHERE us.user_id = %s
              AND b.budget_id = %s
            ORDER BY c.category_name ASC
            """,
            (user_id, budget_id),
        )
        rows = cursor.fetchall()
        if not rows:
            _raise_budget_missing_or_forbidden(cursor, user_id=user_id, budget_id=budget_id)

        grouped = _group_budget_rows(rows)
        return grouped[0]
    finally:
        cursor.close()
        conn.close()


def create_budget(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new budget linked to the user and categories."""

    data = _normalize_payload(payload)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        _assert_categories_available(cursor, user_id=user_id, category_ids=data["category_ids"])

        conn.start_transaction()

        cursor.execute(
            """
            INSERT INTO budget (budget_name, budget_month, monthly_limit)
            VALUES (%s, %s, %s)
            """,
            (data["budget_name"], data["budget_month"], data["monthly_limit"]),
        )
        budget_id = int(cursor.lastrowid)

        cursor.execute(
            "INSERT INTO user_sets (user_id, budget_id) VALUES (%s, %s)",
            (user_id, budget_id),
        )

        cursor.executemany(
            "INSERT INTO applies_to (budget_id, category_id) VALUES (%s, %s)",
            [(budget_id, category_id) for category_id in data["category_ids"]],
        )

        conn.commit()
        return get_budget_by_id_for_user(user_id, budget_id)
    except BudgetServiceError:
        conn.rollback()
        raise
    except mysql.connector.Error as exc:
        conn.rollback()
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise BudgetValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def update_budget(user_id: int, budget_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Update a budget if it belongs only to this user."""

    data = _normalize_payload(payload)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        _assert_budget_updatable_by_user(cursor, user_id=user_id, budget_id=budget_id)
        _assert_categories_available(cursor, user_id=user_id, category_ids=data["category_ids"])

        conn.start_transaction()

        cursor.execute(
            """
            UPDATE budget
            SET budget_name = %s,
                budget_month = %s,
                monthly_limit = %s
            WHERE budget_id = %s
            """,
            (
                data["budget_name"],
                data["budget_month"],
                data["monthly_limit"],
                budget_id,
            ),
        )

        cursor.execute("DELETE FROM applies_to WHERE budget_id = %s", (budget_id,))
        cursor.executemany(
            "INSERT INTO applies_to (budget_id, category_id) VALUES (%s, %s)",
            [(budget_id, category_id) for category_id in data["category_ids"]],
        )

        conn.commit()
        return get_budget_by_id_for_user(user_id, budget_id)
    except BudgetServiceError:
        conn.rollback()
        raise
    except mysql.connector.Error as exc:
        conn.rollback()
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise BudgetValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def delete_budget(user_id: int, budget_id: int) -> None:
    """Delete user's budget mapping, and delete budget record if no users remain."""

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT 1 FROM user_sets WHERE user_id = %s AND budget_id = %s",
            (user_id, budget_id),
        )
        owned = cursor.fetchone()
        if owned is None:
            _raise_budget_missing_or_forbidden(cursor, user_id=user_id, budget_id=budget_id)

        cursor.execute(
            "SELECT COUNT(*) AS user_count FROM user_sets WHERE budget_id = %s",
            (budget_id,),
        )
        user_count = int(cursor.fetchone()["user_count"])

        conn.start_transaction()
        cursor.execute(
            "DELETE FROM user_sets WHERE user_id = %s AND budget_id = %s",
            (user_id, budget_id),
        )

        if user_count <= 1:
            cursor.execute("DELETE FROM applies_to WHERE budget_id = %s", (budget_id,))
            cursor.execute("DELETE FROM budget WHERE budget_id = %s", (budget_id,))

        conn.commit()
    except BudgetServiceError:
        conn.rollback()
        raise
    except mysql.connector.Error as exc:
        conn.rollback()
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise BudgetValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def _assert_budget_updatable_by_user(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    budget_id: int,
) -> None:
    """Ensure user owns budget and it is not shared with other users."""

    cursor.execute(
        "SELECT 1 FROM user_sets WHERE user_id = %s AND budget_id = %s",
        (user_id, budget_id),
    )
    owned = cursor.fetchone()
    if owned is None:
        _raise_budget_missing_or_forbidden(cursor, user_id=user_id, budget_id=budget_id)

    cursor.execute(
        "SELECT COUNT(*) AS user_count FROM user_sets WHERE budget_id = %s",
        (budget_id,),
    )
    user_count = int(cursor.fetchone()["user_count"])

    if user_count > 1:
        raise BudgetForbiddenError(
            "Shared budgets cannot be edited from this endpoint."
        )


def _assert_categories_available(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    category_ids: list[int],
) -> None:
    """Ensure all selected categories are available to this user."""

    placeholders = ", ".join(["%s"] * len(category_ids))
    params: list[Any] = [user_id, *category_ids]

    cursor.execute(
        f"""
        SELECT DISTINCT c.category_id
        FROM category c
        LEFT JOIN defines d ON d.category_id = c.category_id AND d.user_id = %s
        WHERE c.category_id IN ({placeholders})
          AND (c.is_system_category = 1 OR d.user_id IS NOT NULL)
        """,
        tuple(params),
    )
    rows = cursor.fetchall()

    available_ids = {int(row["category_id"]) for row in rows}
    missing = [category_id for category_id in category_ids if category_id not in available_ids]
    if missing:
        raise BudgetForbiddenError(
            "One or more selected categories are not available for this user."
        )


def _raise_budget_missing_or_forbidden(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    budget_id: int,
) -> None:
    """Raise proper exception based on existence and ownership."""

    cursor.execute("SELECT budget_id FROM budget WHERE budget_id = %s", (budget_id,))
    exists = cursor.fetchone()
    if not exists:
        raise BudgetNotFoundError("Budget not found.")

    cursor.execute(
        "SELECT 1 FROM user_sets WHERE user_id = %s AND budget_id = %s",
        (user_id, budget_id),
    )
    user_link = cursor.fetchone()
    if user_link is None:
        raise BudgetForbiddenError("You do not have access to this budget.")

    raise BudgetNotFoundError("Budget not found.")


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate create/update payload."""

    budget_name = str(payload.get("budget_name", "")).strip()
    if not budget_name:
        raise BudgetValidationError("budget_name is required.")
    if len(budget_name) > 100:
        raise BudgetValidationError("budget_name must be 100 characters or fewer.")

    budget_month = _normalize_month(payload.get("budget_month"))
    if budget_month is None:
        raise BudgetValidationError("budget_month is required in YYYY-MM or YYYY-MM-DD format.")

    try:
        monthly_limit = Decimal(str(payload.get("monthly_limit"))).quantize(Decimal("0.01"))
    except Exception as exc:
        raise BudgetValidationError("monthly_limit must be a valid decimal number.") from exc

    if monthly_limit < 0:
        raise BudgetValidationError("monthly_limit must be non-negative.")

    category_ids = _normalize_category_ids(payload.get("category_ids"))
    if not category_ids:
        raise BudgetValidationError("At least one category must be selected.")

    return {
        "budget_name": budget_name,
        "budget_month": budget_month,
        "monthly_limit": monthly_limit,
        "category_ids": category_ids,
    }


def _normalize_month(raw_value: Any) -> date | None:
    """Parse month in YYYY-MM or YYYY-MM-DD format into first day of month."""

    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed.replace(day=1)
        except ValueError:
            continue

    raise BudgetValidationError("month must be in YYYY-MM or YYYY-MM-DD format.")


def _normalize_category_ids(raw_value: Any) -> list[int]:
    """Parse category IDs from list, comma-separated string, or scalar."""

    if raw_value is None:
        return []

    values: list[Any]
    if isinstance(raw_value, list):
        values = raw_value
    elif isinstance(raw_value, tuple):
        values = list(raw_value)
    elif isinstance(raw_value, str):
        values = [chunk.strip() for chunk in raw_value.split(",") if chunk.strip()]
    else:
        values = [raw_value]

    parsed: list[int] = []
    for value in values:
        try:
            category_id = int(value)
        except (TypeError, ValueError) as exc:
            raise BudgetValidationError("category_ids must contain integers.") from exc
        parsed.append(category_id)

    deduped = sorted(set(parsed))
    return deduped


def _group_budget_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group joined budget rows into nested budget records with categories list."""

    grouped: dict[int, dict[str, Any]] = {}

    for row in rows:
        budget_id = int(row["budget_id"])
        existing = grouped.get(budget_id)

        if existing is None:
            budget_month = row.get("budget_month")
            monthly_limit = row.get("monthly_limit")

            existing = {
                "budget_id": budget_id,
                "budget_name": row.get("budget_name"),
                "budget_month": (
                    budget_month.isoformat() if isinstance(budget_month, (date, datetime)) else budget_month
                ),
                "monthly_limit": float(monthly_limit) if isinstance(monthly_limit, Decimal) else monthly_limit,
                "categories": [],
                "category_ids": [],
            }
            grouped[budget_id] = existing

        category_id = row.get("category_id")
        if category_id is not None:
            category_obj = {
                "category_id": int(category_id),
                "category_name": row.get("category_name"),
                "category_type": row.get("category_type"),
            }
            existing["categories"].append(category_obj)
            existing["category_ids"].append(int(category_id))

    return list(grouped.values())
