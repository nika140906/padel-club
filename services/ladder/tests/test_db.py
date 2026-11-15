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


def test_init_db_creates_only_the_ladder_tables(db_path):
    conn = connect(db_path)

    assert table_names(conn) == {"players", "matches"}


def test_init_db_can_run_twice(db_path):
    init_db(db_path)

    assert table_names(connect(db_path)) == {"players", "matches"}


def test_match_players_must_be_on_the_ladder(db_path):
    conn = connect(db_path)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO matches (team_a_p1, team_a_p2, team_b_p1, team_b_p2, winner, recorded_by) "
            "VALUES (1, 2, 3, 4, 'A', 1)"
        )


def test_match_winner_must_be_a_or_b(db_path):
    conn = connect(db_path)
    for user_id in (1, 2, 3, 4):
        conn.execute(
            "INSERT INTO players (user_id, nickname) VALUES (?, ?)", (user_id, f"p{user_id}")
        )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO matches (team_a_p1, team_a_p2, team_b_p1, team_b_p2, winner, recorded_by) "
            "VALUES (1, 2, 3, 4, 'C', 1)"
        )
