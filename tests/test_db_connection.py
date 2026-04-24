from unittest.mock import Mock, patch

from app import create_app
from app.db.connection import get_mysql_connection


def _base_config() -> dict[str, object]:
    return {
        "TESTING": True,
        "MYSQL_USER": "finance_app",
        "MYSQL_PASSWORD": "secret",
        "MYSQL_DATABASE": "tracker",
        "MYSQL_HOST": "127.0.0.1",
        "MYSQL_PORT": 3306,
        "MYSQL_UNIX_SOCKET": "",
        "INSTANCE_CONNECTION_NAME": "",
    }


def test_get_mysql_connection_uses_host_port_outside_cloud_run():
    app = create_app(
        {
            **_base_config(),
            "INSTANCE_CONNECTION_NAME": "project:region:instance",
        }
    )

    with app.app_context():
        with patch("app.db.connection.mysql.connector.connect", return_value=Mock()) as connect_mock:
            with patch.dict("os.environ", {}, clear=False):
                get_mysql_connection()

    connect_mock.assert_called_once_with(
        user="finance_app",
        password="secret",
        database="tracker",
        host="127.0.0.1",
        port=3306,
    )


def test_get_mysql_connection_uses_cloud_sql_socket_on_cloud_run():
    app = create_app(
        {
            **_base_config(),
            "INSTANCE_CONNECTION_NAME": "project:region:instance",
        }
    )

    with app.app_context():
        with patch("app.db.connection.mysql.connector.connect", return_value=Mock()) as connect_mock:
            with patch.dict("os.environ", {"K_SERVICE": "finance-tracker"}, clear=False):
                get_mysql_connection()

    connect_mock.assert_called_once_with(
        user="finance_app",
        password="secret",
        database="tracker",
        unix_socket="/cloudsql/project:region:instance",
    )


def test_get_mysql_connection_prefers_explicit_unix_socket():
    app = create_app(
        {
            **_base_config(),
            "MYSQL_UNIX_SOCKET": "/tmp/mysql.sock",
            "INSTANCE_CONNECTION_NAME": "project:region:instance",
        }
    )

    with app.app_context():
        with patch("app.db.connection.mysql.connector.connect", return_value=Mock()) as connect_mock:
            with patch.dict("os.environ", {}, clear=False):
                get_mysql_connection()

    connect_mock.assert_called_once_with(
        user="finance_app",
        password="secret",
        database="tracker",
        unix_socket="/tmp/mysql.sock",
    )
