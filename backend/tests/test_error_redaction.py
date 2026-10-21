import logging

from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from app.db.session import Database
from app.errors import _database_unavailable_handler


def _request(path: str = "/services") -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 1234),
        }
    )


def test_database_unavailable_handler_redacts_driver_exception(caplog):
    secret_dsn = "postgresql://test_user:fake_password@db.internal/testdb"
    error = OperationalError("SELECT 1", {}, Exception(secret_dsn))

    with caplog.at_level(logging.WARNING):
        response = _database_unavailable_handler(_request(), error)

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert secret_dsn not in caplog.text
    assert secret_dsn.encode() not in response.body
    assert "OperationalError" in caplog.text


def test_startup_schema_check_redacts_driver_exception(monkeypatch, caplog):
    secret_dsn = "postgresql://test_user:fake_password@db.internal/testdb"
    database = Database("sqlite://")

    def fail_schema_check(_engine):
        raise OperationalError("SELECT 1", {}, Exception(secret_dsn))

    monkeypatch.setattr("app.db.session.schema_problems", fail_schema_check)

    try:
        with caplog.at_level(logging.WARNING):
            database.verify_schema()

        assert secret_dsn not in caplog.text
        assert "OperationalError" in caplog.text
    finally:
        database.dispose()
