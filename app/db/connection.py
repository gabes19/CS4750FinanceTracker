"""Reusable MySQL connection helper."""

from __future__ import annotations

import os

import mysql.connector
from flask import current_app
from mysql.connector import MySQLConnection


def get_mysql_connection() -> MySQLConnection:
    """Create and return a new MySQL connection using app config."""

    connection_kwargs = {
        "user": current_app.config["MYSQL_USER"],
        "password": current_app.config["MYSQL_PASSWORD"],
        "database": current_app.config["MYSQL_DATABASE"],
    }

    unix_socket = _resolve_unix_socket()

    if unix_socket:
        connection_kwargs["unix_socket"] = unix_socket
    else:
        connection_kwargs["host"] = current_app.config["MYSQL_HOST"]
        connection_kwargs["port"] = current_app.config["MYSQL_PORT"]

    return mysql.connector.connect(**connection_kwargs)


def _resolve_unix_socket() -> str:
    """Return the configured Unix socket path when socket mode should be used."""

    explicit_socket = current_app.config.get("MYSQL_UNIX_SOCKET", "").strip()
    if explicit_socket:
        return explicit_socket

    instance_connection_name = current_app.config.get("INSTANCE_CONNECTION_NAME", "").strip()
    if instance_connection_name and _is_running_on_cloud_run():
        return f"/cloudsql/{instance_connection_name}"

    return ""


def _is_running_on_cloud_run() -> bool:
    """Detect whether the current process is running inside Cloud Run."""

    return bool(os.getenv("K_SERVICE") or os.getenv("K_REVISION"))
