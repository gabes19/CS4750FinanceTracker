"""Dashboard aggregate queries for user-scoped monthly insights."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.db.connection import get_mysql_connection


def get_dashboard_snapshot(user_id: int, month: str | None = None) -> dict[str, Any]:
    """Return dashboard summary and chart datasets for a month."""

    month_start = _normalize_month(month)
    month_end = _next_month(month_start)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        totals = _get_month_totals(cursor, user_id=user_id, month_start=month_start, month_end=month_end)
        spending_by_category = _get_spending_by_category(
            cursor,
            user_id=user_id,
            month_start=month_start,
            month_end=month_end,
        )
        budget_remaining = _get_budget_remaining_by_category(
            cursor,
            user_id=user_id,
            month_start=month_start,
            month_end=month_end,
        )
        totals["remaining_budget"] = float(
            sum(Decimal(str(row["remaining"])) for row in budget_remaining)
        )

        return {
            "month": month_start.strftime("%Y-%m"),
            "totals": totals,
            "spending_by_category": spending_by_category,
            "budget_remaining_by_category": budget_remaining,
        }
    finally:
        cursor.close()
        conn.close()


def _get_month_totals(
    cursor,
    user_id: int,
    month_start: date,
    month_end: date,
) -> dict[str, float]:
    """Fetch monthly income and expenses for user."""

    cursor.execute(
        """
        SELECT COALESCE(SUM(t.amount), 0) AS total_income
        FROM `transaction` t
        INNER JOIN records r ON r.transaction_id = t.transaction_id
        WHERE r.user_id = %s
          AND t.transaction_type = 'income'
          AND t.transaction_date >= %s
          AND t.transaction_date < %s
        """,
        (user_id, month_start, month_end),
    )
    income = Decimal(cursor.fetchone()["total_income"])

    cursor.execute(
        """
        SELECT COALESCE(SUM(t.amount), 0) AS total_expenses
        FROM `transaction` t
        INNER JOIN records r ON r.transaction_id = t.transaction_id
        WHERE r.user_id = %s
          AND t.transaction_type = 'expense'
          AND t.transaction_date >= %s
          AND t.transaction_date < %s
        """,
        (user_id, month_start, month_end),
    )
    expenses = Decimal(cursor.fetchone()["total_expenses"])

    return {
        "income": float(income),
        "expenses": float(expenses),
        "remaining_budget": 0.0,
    }


def _get_spending_by_category(
    cursor,
    user_id: int,
    month_start: date,
    month_end: date,
) -> list[dict[str, Any]]:
    """Fetch monthly expense totals grouped by category."""

    cursor.execute(
        """
        SELECT
          c.category_id,
          c.category_name,
          COALESCE(SUM(t.amount), 0) AS total_spent
        FROM records r
        INNER JOIN `transaction` t ON t.transaction_id = r.transaction_id
        INNER JOIN categorized_as ca ON ca.transaction_id = t.transaction_id
        INNER JOIN category c ON c.category_id = ca.category_id
        WHERE r.user_id = %s
          AND t.transaction_type = 'expense'
          AND t.transaction_date >= %s
          AND t.transaction_date < %s
        GROUP BY c.category_id, c.category_name
        ORDER BY total_spent DESC, c.category_name ASC
        """,
        (user_id, month_start, month_end),
    )

    rows = cursor.fetchall()
    return [
        {
            "category_id": int(row["category_id"]),
            "category_name": row["category_name"],
            "total_spent": float(Decimal(row["total_spent"])),
        }
        for row in rows
    ]


def _get_budget_remaining_by_category(
    cursor,
    user_id: int,
    month_start: date,
    month_end: date,
) -> list[dict[str, Any]]:
    """Fetch monthly budget-vs-spend remaining grouped by category."""

    cursor.execute(
        """
        SELECT
          c.category_id,
          c.category_name,
          COALESCE(SUM(ap.allocated_limit), 0) AS total_budget,
          COALESCE(spent.spent_amount, 0) AS total_spent,
          COALESCE(SUM(ap.allocated_limit), 0) - COALESCE(spent.spent_amount, 0) AS remaining
        FROM user_sets us
        INNER JOIN budget b ON b.budget_id = us.budget_id
        INNER JOIN applies_to ap ON ap.budget_id = b.budget_id
        INNER JOIN category c ON c.category_id = ap.category_id
        LEFT JOIN (
          SELECT
            ca.category_id,
            COALESCE(SUM(t.amount), 0) AS spent_amount
          FROM records r
          INNER JOIN `transaction` t ON t.transaction_id = r.transaction_id
          INNER JOIN categorized_as ca ON ca.transaction_id = t.transaction_id
          WHERE r.user_id = %s
            AND t.transaction_type = 'expense'
            AND t.transaction_date >= %s
            AND t.transaction_date < %s
          GROUP BY ca.category_id
        ) spent ON spent.category_id = c.category_id
        WHERE us.user_id = %s
          AND b.budget_month = %s
        GROUP BY c.category_id, c.category_name, spent.spent_amount
        ORDER BY c.category_name ASC
        """,
        (user_id, month_start, month_end, user_id, month_start),
    )

    rows = cursor.fetchall()
    return [
        {
            "category_id": int(row["category_id"]),
            "category_name": row["category_name"],
            "budgeted": float(Decimal(row["total_budget"])),
            "spent": float(Decimal(row["total_spent"])),
            "remaining": float(Decimal(row["remaining"])),
        }
        for row in rows
    ]


def _normalize_month(raw_month: str | None) -> date:
    """Normalize requested month to first day; defaults to current month."""

    if raw_month is None or not str(raw_month).strip():
        today = date.today()
        return today.replace(day=1)

    text = str(raw_month).strip()
    for fmt in ("%Y-%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed.replace(day=1)
        except ValueError:
            continue

    raise ValueError("month must be in YYYY-MM or YYYY-MM-DD format")


def _next_month(month_start: date) -> date:
    """Return first day of next month."""

    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)
