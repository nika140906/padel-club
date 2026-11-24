from datetime import datetime

import pymssql
import pytest

from padel.db import connect, parse_database_url


def table_names(conn):
    rows = conn.execute("SELECT TABLE_NAME AS name FROM INFORMATION_SCHEMA.TABLES").fetchall()
    return {row["name"] for row in rows}


def test_parse_database_url_splits_all_parts():
    settings = parse_database_url("mssql://bookings_user:p%40ss@db:1433/bookings")

    assert settings == {
        "server": "db",
        "port": 1433,
        "user": "bookings_user",
        "password": "p@ss",
        "database": "bookings",
    }


def test_parse_database_url_uses_port_1433_by_default():
    assert parse_database_url("mssql://u:p@db/bookings")["port"] == 1433


@pytest.mark.parametrize("url", [None, "", "sqlite:///bookings.db", "mssql://u:p@db"])
def test_parse_database_url_rejects_other_urls(url):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        parse_database_url(url)


def test_parse_database_url_requires_encryption_when_asked():
    settings = parse_database_url("mssql://u:p@x.database.windows.net:1433/db?encrypt=true")

    assert settings["encryption"] == "require"
    assert settings["database"] == "db"


def test_parse_database_url_leaves_encryption_to_pymssql_by_default():
    assert "encryption" not in parse_database_url("mssql://u:p@db:1433/db")


class FakePymssql:
    """Stands in for pymssql.connect: fails with the given error numbers, then connects."""

    def __init__(self, *error_numbers):
        self.errors = list(error_numbers)
        self.calls = []

    def connect(self, **settings):
        self.calls.append(settings)
        if self.errors:
            number = self.errors.pop(0)
            raise pymssql.OperationalError((number, b"DB-Lib error message"))
        return "raw connection"


@pytest.fixture
def fake_pymssql(monkeypatch):
    def install(*error_numbers):
        fake = FakePymssql(*error_numbers)
        monkeypatch.setattr("padel.db.pymssql.connect", fake.connect)
        return fake

    return install


@pytest.fixture
def sleeps(monkeypatch):
    """Records each wait instead of really sleeping."""
    waited = []
    monkeypatch.setattr("padel.db.time.sleep", waited.append)
    return waited


@pytest.mark.parametrize("number", [40613, 20002, 20003])
def test_connect_retries_while_the_database_is_not_ready(fake_pymssql, sleeps, number):
    fake = fake_pymssql(number, number)

    conn = connect("mssql://u:p@db/x", retry_delays=(1, 2, 4), login_timeout=15)

    assert conn.raw == "raw connection"
    assert sleeps == [1, 2]
    assert len(fake.calls) == 3
    assert fake.calls[0]["login_timeout"] == 15


def test_connect_gives_up_after_the_last_delay(fake_pymssql, sleeps):
    fake = fake_pymssql(40613, 40613, 40613)

    with pytest.raises(pymssql.OperationalError):
        connect("mssql://u:p@db/x", retry_delays=(1, 2))

    assert sleeps == [1, 2]
    assert len(fake.calls) == 3


def test_connect_does_not_retry_other_errors(fake_pymssql, sleeps):
    fake = fake_pymssql(18456)  # login failed: waiting will not fix a wrong password

    with pytest.raises(pymssql.OperationalError):
        connect("mssql://u:p@db/x", retry_delays=(1, 2))

    assert sleeps == []
    assert len(fake.calls) == 1


def test_connect_tries_once_without_delays(fake_pymssql, sleeps):
    fake = fake_pymssql(40613)

    with pytest.raises(pymssql.OperationalError):
        connect("mssql://u:p@db/x")

    assert sleeps == []
    assert len(fake.calls) == 1


def test_migrations_create_all_tables(conn):
    assert table_names(conn) == {"schema_migrations", "users", "courts", "bookings"}


def test_migrations_seed_four_courts(conn):
    count = conn.execute("SELECT COUNT(*) AS n FROM courts").fetchone()["n"]

    assert count == 4


def test_usernames_are_case_sensitive(conn):
    conn.execute("INSERT INTO users (username, password_hash) VALUES ('nika', 'x')")
    conn.execute("INSERT INTO users (username, password_hash) VALUES ('Nika', 'x')")

    count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]

    assert count == 2


def test_booking_court_must_exist(conn):
    with pytest.raises(pymssql.IntegrityError):
        conn.execute(
            "INSERT INTO bookings (court_id, user_id, start_time, end_time) "
            "VALUES (999, 1, %s, %s)",
            (datetime(2026, 10, 1, 18), datetime(2026, 10, 1, 19, 30)),
        )


def test_booking_must_end_after_it_starts(conn):
    with pytest.raises(pymssql.IntegrityError):
        conn.execute(
            "INSERT INTO bookings (court_id, user_id, start_time, end_time) "
            "VALUES (1, 1, %s, %s)",
            (datetime(2026, 10, 1, 19), datetime(2026, 10, 1, 18)),
        )
