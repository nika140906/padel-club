import sqlite3

import pytest

from padel.db import connect, get_db_path, init_db


@pytest.fixture
def db_path(tmp_path):
    path = get_db_path(str(tmp_path))
    init_db(path)
    return path


def table_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row["name"] for row in rows}


def test_init_db_creates_all_tables(db_path):
    conn = connect(db_path)

    assert table_names(conn) == {"users", "courts", "bookings", "players", "matches"}


def test_init_db_seeds_four_courts(db_path):
    conn = connect(db_path)

    count = conn.execute("SELECT COUNT(*) FROM courts").fetchone()[0]

    assert count == 4


def test_init_db_can_run_twice_without_duplicating_courts(db_path):
    init_db(db_path)
    conn = connect(db_path)

    count = conn.execute("SELECT COUNT(*) FROM courts").fetchone()[0]

    assert count == 4


def test_foreign_keys_are_enforced(db_path):
    conn = connect(db_path)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO bookings (court_id, user_id, start_time, end_time) "
            "VALUES (999, 1, '2026-10-01 18:00', '2026-10-01 19:30')"
        )


def test_booking_must_end_after_it_starts(db_path):
    conn = connect(db_path)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO bookings (court_id, user_id, start_time, end_time) "
            "VALUES (1, 1, '2026-10-01 19:00', '2026-10-01 18:00')"
        )


def test_match_winner_must_be_a_or_b(db_path):
    conn = connect(db_path)
    for user_id in (1, 2, 3, 4):
        conn.execute("INSERT INTO players (user_id) VALUES (?)", (user_id,))

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO matches (team_a_p1, team_a_p2, team_b_p1, team_b_p2, winner, recorded_by) "
            "VALUES (1, 2, 3, 4, 'C', 1)"
        )
