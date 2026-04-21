"""Transaction service functions for user-scoped CRUD operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import mysql.connector

from app.db.connection import get_mysql_connection


class TransactionServiceError(Exception):
    """Base service exception."""

    status_code = 400


class TransactionValidationError(TransactionServiceError):
    """Raised when request payload is invalid or violates business constraints."""

    status_code = 400


class TransactionNotFoundError(TransactionServiceError):
    """Raised when a transaction cannot be found."""

    status_code = 404


class TransactionForbiddenError(TransactionServiceError):
    """Raised when a user attempts unauthorized transaction access."""

    status_code = 403


@dataclass
class TransactionFilters:
    """Query filter options for listing transactions."""

    start_date: str | None = None
    end_date: str | None = None
    category_id: int | None = None
    account_id: int | None = None
    keyword: str | None = None
    sort_by: str = "date"
    sort_dir: str = "desc"


def list_user_accounts(user_id: int) -> list[dict[str, Any]]:
    """Return accounts owned or visible to a user."""

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT a.account_id, a.account_name, a.account_type, o.ownership_role
            FROM owns o
            INNER JOIN account a ON a.account_id = o.account_id
            WHERE o.user_id = %s
            ORDER BY a.account_name ASC
            """,
            (user_id,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def list_user_categories(user_id: int) -> list[dict[str, Any]]:
    """Return categories available to a user (system or user-defined)."""

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


def list_user_transactions(user_id: int, filters: TransactionFilters) -> list[dict[str, Any]]:
    """Return filtered and sorted transactions for a single user."""

    allowed_sort_columns = {
        "date": "t.transaction_date",
        "amount": "t.amount",
    }
    sort_column = allowed_sort_columns.get(filters.sort_by, "t.transaction_date")
    sort_dir = "ASC" if str(filters.sort_dir).lower() == "asc" else "DESC"

    params: list[Any] = [user_id]
    where_clauses = ["r.user_id = %s"]

    if filters.start_date:
        where_clauses.append("t.transaction_date >= %s")
        params.append(filters.start_date)

    if filters.end_date:
        where_clauses.append("t.transaction_date <= %s")
        params.append(filters.end_date)

    if filters.category_id:
        where_clauses.append(
            """
            EXISTS (
              SELECT 1 FROM categorized_as ca
              WHERE ca.transaction_id = t.transaction_id
                AND ca.category_id = %s
            )
            """
        )
        params.append(filters.category_id)

    if filters.account_id:
        where_clauses.append(
            """
            EXISTS (
              SELECT 1 FROM posts_to pt
              WHERE pt.transaction_id = t.transaction_id
                AND pt.account_id = %s
            )
            """
        )
        params.append(filters.account_id)

    if filters.keyword:
        where_clauses.append("LOWER(COALESCE(t.description, '')) LIKE %s")
        params.append(f"%{filters.keyword.lower()}%")

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = f"""
            SELECT
              t.transaction_id,
              t.transaction_type,
              t.amount,
              t.description,
              t.transaction_date,
              (
                SELECT a.account_id
                FROM posts_to pt
                INNER JOIN account a ON a.account_id = pt.account_id
                WHERE pt.transaction_id = t.transaction_id
                ORDER BY pt.posted_at ASC
                LIMIT 1
              ) AS account_id,
              (
                SELECT a.account_name
                FROM posts_to pt
                INNER JOIN account a ON a.account_id = pt.account_id
                WHERE pt.transaction_id = t.transaction_id
                ORDER BY pt.posted_at ASC
                LIMIT 1
              ) AS account_name,
              (
                SELECT c.category_id
                FROM categorized_as ca
                INNER JOIN category c ON c.category_id = ca.category_id
                WHERE ca.transaction_id = t.transaction_id
                ORDER BY ca.categorized_at ASC
                LIMIT 1
              ) AS category_id,
              (
                SELECT c.category_name
                FROM categorized_as ca
                INNER JOIN category c ON c.category_id = ca.category_id
                WHERE ca.transaction_id = t.transaction_id
                ORDER BY ca.categorized_at ASC
                LIMIT 1
              ) AS category_name
            FROM `transaction` t
            INNER JOIN records r ON r.transaction_id = t.transaction_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY {sort_column} {sort_dir}, t.transaction_id DESC
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [_serialize_transaction_row(row) for row in rows]
    finally:
        cursor.close()
        conn.close()


def create_transaction(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a transaction for a user, preferring the stored procedure path."""

    data = _normalize_payload(payload)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        _assert_account_access(cursor, user_id=user_id, account_id=data["account_id"])
        _assert_category_access(cursor, user_id=user_id, category_id=data["category_id"])
        _assert_category_type_matches_transaction_type(
            cursor,
            category_id=data["category_id"],
            transaction_type=data["transaction_type"],
        )

        try:
            transaction_id = _create_transaction_via_procedure(
                conn,
                user_id=user_id,
                data=data,
            )
        except mysql.connector.Error as exc:
            if exc.errno == 1305:
                transaction_id = _create_transaction_manual(
                    conn,
                    cursor,
                    user_id=user_id,
                    data=data,
                )
            else:
                raise

        return get_transaction_by_id_for_user(user_id, transaction_id)
    except TransactionServiceError:
        raise
    except mysql.connector.Error as exc:
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise TransactionValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def update_transaction(user_id: int, transaction_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Update a user's transaction and associated relationship-table links."""

    data = _normalize_payload(payload)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        existing = _get_user_transaction_row(cursor, user_id=user_id, transaction_id=transaction_id)
        if existing is None:
            _raise_for_missing_or_forbidden(cursor, user_id=user_id, transaction_id=transaction_id)

        _assert_account_access(cursor, user_id=user_id, account_id=data["account_id"])
        _assert_category_access(cursor, user_id=user_id, category_id=data["category_id"])
        _assert_category_type_matches_transaction_type(
            cursor,
            category_id=data["category_id"],
            transaction_type=data["transaction_type"],
        )
        _assert_budget_limit(
            cursor,
            user_id=user_id,
            category_id=data["category_id"],
            transaction_type=data["transaction_type"],
            transaction_date=data["transaction_date"],
            amount=data["amount"],
            exclude_transaction_id=transaction_id,
        )

        conn.start_transaction()

        _apply_balance_delta(
            cursor,
            account_id=existing["account_id"],
            delta=-_signed_amount(existing["transaction_type"], existing["amount"]),
        )

        cursor.execute(
            """
            UPDATE `transaction`
            SET transaction_type = %s,
                amount = %s,
                description = %s,
                transaction_date = %s
            WHERE transaction_id = %s
            """,
            (
                data["transaction_type"],
                data["amount"],
                data["description"],
                data["transaction_date"],
                transaction_id,
            ),
        )

        cursor.execute(
            "DELETE FROM posts_to WHERE transaction_id = %s",
            (transaction_id,),
        )
        cursor.execute(
            "INSERT INTO posts_to (transaction_id, account_id) VALUES (%s, %s)",
            (transaction_id, data["account_id"]),
        )

        cursor.execute(
            "DELETE FROM categorized_as WHERE transaction_id = %s",
            (transaction_id,),
        )
        cursor.execute(
            "INSERT INTO categorized_as (transaction_id, category_id) VALUES (%s, %s)",
            (transaction_id, data["category_id"]),
        )

        _apply_balance_delta(
            cursor,
            account_id=data["account_id"],
            delta=_signed_amount(data["transaction_type"], data["amount"]),
        )

        conn.commit()
        return get_transaction_by_id_for_user(user_id, transaction_id)
    except TransactionServiceError:
        conn.rollback()
        raise
    except mysql.connector.Error as exc:
        conn.rollback()
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise TransactionValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def delete_transaction(user_id: int, transaction_id: int) -> None:
    """Delete a transaction if it belongs to the user."""

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        existing = _get_user_transaction_row(cursor, user_id=user_id, transaction_id=transaction_id)
        if existing is None:
            _raise_for_missing_or_forbidden(cursor, user_id=user_id, transaction_id=transaction_id)

        cursor.execute(
            "SELECT COUNT(*) AS record_count FROM records WHERE transaction_id = %s",
            (transaction_id,),
        )
        record_count = int(cursor.fetchone()["record_count"])

        if record_count > 1:
            raise TransactionForbiddenError(
                "Cannot delete a transaction recorded by multiple users."
            )

        conn.start_transaction()

        _apply_balance_delta(
            cursor,
            account_id=existing["account_id"],
            delta=-_signed_amount(existing["transaction_type"], existing["amount"]),
        )

        cursor.execute("DELETE FROM categorized_as WHERE transaction_id = %s", (transaction_id,))
        cursor.execute("DELETE FROM posts_to WHERE transaction_id = %s", (transaction_id,))
        cursor.execute(
            "DELETE FROM records WHERE transaction_id = %s AND user_id = %s",
            (transaction_id, user_id),
        )
        cursor.execute(
            "DELETE FROM `transaction` WHERE transaction_id = %s",
            (transaction_id,),
        )

        conn.commit()
    except TransactionServiceError:
        conn.rollback()
        raise
    except mysql.connector.Error as exc:
        conn.rollback()
        message = str(exc.msg) if hasattr(exc, "msg") else str(exc)
        raise TransactionValidationError(message) from exc
    finally:
        cursor.close()
        conn.close()


def get_transaction_by_id_for_user(user_id: int, transaction_id: int) -> dict[str, Any]:
    """Fetch a single transaction owned by a user."""

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        row = _get_user_transaction_row(cursor, user_id=user_id, transaction_id=transaction_id)
        if row is None:
            _raise_for_missing_or_forbidden(cursor, user_id=user_id, transaction_id=transaction_id)
        return _serialize_transaction_row(row)
    finally:
        cursor.close()
        conn.close()


def _create_transaction_via_procedure(
    conn: mysql.connector.MySQLConnection,
    user_id: int,
    data: dict[str, Any],
) -> int:
    """Create transaction by calling the stored procedure."""

    proc_cursor = conn.cursor()
    try:
        proc_cursor.callproc(
            "sp_add_transaction",
            [
                user_id,
                data["account_id"],
                data["category_id"],
                data["transaction_type"],
                data["amount"],
                data["description"],
                data["transaction_date"],
            ],
        )

        transaction_id: int | None = None
        for result in proc_cursor.stored_results():
            row = result.fetchone()
            if row:
                transaction_id = int(row[0])

        if transaction_id is None:
            raise TransactionValidationError("Stored procedure did not return a transaction ID.")

        return transaction_id
    finally:
        proc_cursor.close()


def _create_transaction_manual(
    conn: mysql.connector.MySQLConnection,
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    data: dict[str, Any],
) -> int:
    """Fallback create path when stored procedure is unavailable."""

    _assert_budget_limit(
        cursor,
        user_id=user_id,
        category_id=data["category_id"],
        transaction_type=data["transaction_type"],
        transaction_date=data["transaction_date"],
        amount=data["amount"],
        exclude_transaction_id=None,
    )

    conn.start_transaction()
    try:
        cursor.execute(
            """
            INSERT INTO `transaction` (transaction_type, amount, description, transaction_date)
            VALUES (%s, %s, %s, %s)
            """,
            (
                data["transaction_type"],
                data["amount"],
                data["description"],
                data["transaction_date"],
            ),
        )
        transaction_id = int(cursor.lastrowid)

        cursor.execute(
            "INSERT INTO records (user_id, transaction_id) VALUES (%s, %s)",
            (user_id, transaction_id),
        )
        cursor.execute(
            "INSERT INTO posts_to (transaction_id, account_id) VALUES (%s, %s)",
            (transaction_id, data["account_id"]),
        )
        cursor.execute(
            "INSERT INTO categorized_as (transaction_id, category_id) VALUES (%s, %s)",
            (transaction_id, data["category_id"]),
        )

        _apply_balance_delta(
            cursor,
            account_id=data["account_id"],
            delta=_signed_amount(data["transaction_type"], data["amount"]),
        )

        conn.commit()
        return transaction_id
    except Exception:
        conn.rollback()
        raise


def _get_user_transaction_row(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    transaction_id: int,
) -> dict[str, Any] | None:
    """Fetch a transaction row for a user with linked account/category."""

    cursor.execute(
        """
        SELECT
          t.transaction_id,
          t.transaction_type,
          t.amount,
          t.description,
          t.transaction_date,
          (
            SELECT a.account_id
            FROM posts_to pt
            INNER JOIN account a ON a.account_id = pt.account_id
            WHERE pt.transaction_id = t.transaction_id
            ORDER BY pt.posted_at ASC
            LIMIT 1
          ) AS account_id,
          (
            SELECT a.account_name
            FROM posts_to pt
            INNER JOIN account a ON a.account_id = pt.account_id
            WHERE pt.transaction_id = t.transaction_id
            ORDER BY pt.posted_at ASC
            LIMIT 1
          ) AS account_name,
          (
            SELECT c.category_id
            FROM categorized_as ca
            INNER JOIN category c ON c.category_id = ca.category_id
            WHERE ca.transaction_id = t.transaction_id
            ORDER BY ca.categorized_at ASC
            LIMIT 1
          ) AS category_id,
          (
            SELECT c.category_name
            FROM categorized_as ca
            INNER JOIN category c ON c.category_id = ca.category_id
            WHERE ca.transaction_id = t.transaction_id
            ORDER BY ca.categorized_at ASC
            LIMIT 1
          ) AS category_name
        FROM `transaction` t
        INNER JOIN records r ON r.transaction_id = t.transaction_id
        WHERE r.user_id = %s
          AND t.transaction_id = %s
        LIMIT 1
        """,
        (user_id, transaction_id),
    )
    return cursor.fetchone()


def _raise_for_missing_or_forbidden(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    transaction_id: int,
) -> None:
    """Raise a specific error based on existence and ownership."""

    cursor.execute(
        "SELECT transaction_id FROM `transaction` WHERE transaction_id = %s",
        (transaction_id,),
    )
    exists = cursor.fetchone()
    if not exists:
        raise TransactionNotFoundError("Transaction not found.")

    cursor.execute(
        "SELECT 1 FROM records WHERE transaction_id = %s AND user_id = %s",
        (transaction_id, user_id),
    )
    ownership = cursor.fetchone()
    if not ownership:
        raise TransactionForbiddenError("You do not have access to this transaction.")

    raise TransactionNotFoundError("Transaction not found.")


def _assert_account_access(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    account_id: int,
) -> None:
    """Ensure user has access to the target account."""

    cursor.execute(
        "SELECT 1 FROM owns WHERE user_id = %s AND account_id = %s",
        (user_id, account_id),
    )
    if cursor.fetchone() is None:
        raise TransactionForbiddenError("User cannot post to the selected account.")


def _assert_category_access(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    category_id: int,
) -> None:
    """Ensure category is system-defined or owned by user."""

    cursor.execute(
        """
        SELECT c.category_id
        FROM category c
        LEFT JOIN defines d ON d.category_id = c.category_id AND d.user_id = %s
        WHERE c.category_id = %s
          AND (c.is_system_category = 1 OR d.user_id IS NOT NULL)
        LIMIT 1
        """,
        (user_id, category_id),
    )
    if cursor.fetchone() is None:
        raise TransactionForbiddenError("Category is not available for this user.")


def _assert_category_type_matches_transaction_type(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    category_id: int,
    transaction_type: str,
) -> None:
    """Ensure category type and transaction type are aligned."""

    cursor.execute(
        "SELECT category_type FROM category WHERE category_id = %s",
        (category_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise TransactionValidationError("Category does not exist.")

    if row["category_type"] != transaction_type:
        raise TransactionValidationError(
            "Transaction type must match selected category type."
        )


def _assert_budget_limit(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    user_id: int,
    category_id: int,
    transaction_type: str,
    transaction_date: date,
    amount: Decimal,
    exclude_transaction_id: int | None,
) -> None:
    """Block expense inserts/updates that exceed configured monthly budget."""

    if transaction_type != "expense":
        return

    budget_month = transaction_date.replace(day=1)

    cursor.execute(
        """
        SELECT COALESCE(SUM(b.monthly_limit), 0) AS budget_limit
        FROM budget b
        INNER JOIN user_sets us ON us.budget_id = b.budget_id
        INNER JOIN applies_to a ON a.budget_id = b.budget_id
        WHERE us.user_id = %s
          AND a.category_id = %s
          AND b.budget_month = %s
        """,
        (user_id, category_id, budget_month),
    )
    budget_limit = Decimal(cursor.fetchone()["budget_limit"])

    if budget_limit <= 0:
        return

    params: list[Any] = [user_id, category_id, budget_month, budget_month]
    exclusion_sql = ""
    if exclude_transaction_id is not None:
        exclusion_sql = "AND t.transaction_id <> %s"
        params.append(exclude_transaction_id)

    cursor.execute(
        f"""
        SELECT COALESCE(SUM(t.amount), 0) AS spent_this_month
        FROM `transaction` t
        INNER JOIN records r ON r.transaction_id = t.transaction_id
        INNER JOIN categorized_as ca ON ca.transaction_id = t.transaction_id
        WHERE r.user_id = %s
          AND ca.category_id = %s
          AND t.transaction_type = 'expense'
          AND t.transaction_date >= %s
          AND t.transaction_date < DATE_ADD(%s, INTERVAL 1 MONTH)
          {exclusion_sql}
        """,
        tuple(params),
    )
    spent = Decimal(cursor.fetchone()["spent_this_month"])

    if spent + amount > budget_limit:
        raise TransactionValidationError(
            "Expense exceeds this category's monthly budget for the user."
        )


def _apply_balance_delta(
    cursor: mysql.connector.cursor.MySQLCursorDict,
    account_id: int | None,
    delta: Decimal,
) -> None:
    """Apply a signed balance delta to the given account."""

    if account_id is None:
        raise TransactionValidationError("Transaction is missing an account relationship.")

    cursor.execute(
        "UPDATE account SET current_balance = current_balance + %s WHERE account_id = %s",
        (delta, account_id),
    )

    if cursor.rowcount != 1:
        raise TransactionValidationError("Account update failed.")


def _signed_amount(transaction_type: str, amount: Decimal) -> Decimal:
    """Return signed amount impact on account balance."""

    if transaction_type == "income":
        return amount
    if transaction_type == "expense":
        return -amount
    return Decimal("0")


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize API payload for create/update operations."""

    transaction_type = str(payload.get("transaction_type", "")).strip().lower()
    if transaction_type not in {"income", "expense"}:
        raise TransactionValidationError("transaction_type must be income or expense.")

    try:
        amount = Decimal(str(payload.get("amount"))).quantize(Decimal("0.01"))
    except Exception as exc:
        raise TransactionValidationError("amount must be a valid decimal number.") from exc

    if amount <= 0:
        raise TransactionValidationError("amount must be greater than 0.")

    try:
        account_id = int(payload.get("account_id"))
    except (TypeError, ValueError) as exc:
        raise TransactionValidationError("account_id must be an integer.") from exc

    try:
        category_id = int(payload.get("category_id"))
    except (TypeError, ValueError) as exc:
        raise TransactionValidationError("category_id must be an integer.") from exc

    raw_date = str(payload.get("transaction_date", "")).strip()
    try:
        transaction_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise TransactionValidationError("transaction_date must be in YYYY-MM-DD format.") from exc

    description = payload.get("description")
    if description is None:
        description = ""
    description = str(description).strip()

    return {
        "transaction_type": transaction_type,
        "amount": amount,
        "description": description,
        "transaction_date": transaction_date,
        "account_id": account_id,
        "category_id": category_id,
    }


def _serialize_transaction_row(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize database row values for JSON/template safety."""

    result = dict(row)

    date_value = result.get("transaction_date")
    if isinstance(date_value, (date, datetime)):
        result["transaction_date"] = date_value.isoformat()

    amount_value = result.get("amount")
    if isinstance(amount_value, Decimal):
        result["amount"] = float(amount_value)

    return result
