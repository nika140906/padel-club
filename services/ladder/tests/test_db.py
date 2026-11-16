import pymssql
import pytest

from padel.db import parse_database_url


def table_names(conn):
    rows = conn.execute("SELECT TABLE_NAME AS name FROM INFORMATION_SCHEMA.TABLES").fetchall()
    return {row["name"] for row in rows}


def add_players(conn, *user_ids):
    for user_id in user_ids:
        conn.execute(
            "INSERT INTO players (user_id, nickname) VALUES (%s, %s)", (user_id, f"p{user_id}")
        )


def test_parse_database_url_splits_all_parts():
    settings = parse_database_url("mssql://ladder_user:p%40ss@db:1433/ladder")

    assert settings == {
        "server": "db",
        "port": 1433,
        "user": "ladder_user",
        "password": "p@ss",
        "database": "ladder",
    }


@pytest.mark.parametrize("url", [None, "", "sqlite:///ladder.db", "mssql://u:p@db"])
def test_parse_database_url_rejects_other_urls(url):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        parse_database_url(url)


def test_migrations_create_only_the_ladder_tables(conn):
    assert table_names(conn) == {"schema_migrations", "players", "matches"}


def test_new_player_starts_at_1000_with_no_matches(conn):
    add_players(conn, 1)

    row = conn.execute("SELECT rating, matches_played FROM players WHERE user_id = 1").fetchone()

    assert row == {"rating": 1000, "matches_played": 0}


def test_match_players_must_be_on_the_ladder(conn):
    with pytest.raises(pymssql.IntegrityError):
        conn.execute(
            "INSERT INTO matches (team_a_p1, team_a_p2, team_b_p1, team_b_p2, winner, recorded_by) "
            "VALUES (1, 2, 3, 4, 'A', 1)"
        )


def test_match_winner_must_be_a_or_b(conn):
    add_players(conn, 1, 2, 3, 4)

    with pytest.raises(pymssql.IntegrityError):
        conn.execute(
            "INSERT INTO matches (team_a_p1, team_a_p2, team_b_p1, team_b_p2, winner, recorded_by) "
            "VALUES (1, 2, 3, 4, 'C', 1)"
        )
