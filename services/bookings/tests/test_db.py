from datetime import datetime

import pymssql
import pytest

from padel.db import parse_database_url


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
