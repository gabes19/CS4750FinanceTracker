"""Reusable MySQL connection helper."""

from __future__ import annotations

import mysql.connector
from flask import current_app
from mysql.connector import MySQLConnection


def get_mysql_connection() -> MySQLConnection:
    """Create and return a new MySQL connection using app config."""

    return mysql.connector.connect(
        host=current_app.config["MYSQL_HOST"],
        port=current_app.config["MYSQL_PORT"],
        user=current_app.config["MYSQL_USER"],
        password=current_app.config["MYSQL_PASSWORD"],
        database=current_app.config["MYSQL_DATABASE"],
    )
