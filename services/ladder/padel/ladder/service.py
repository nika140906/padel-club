import re
import sqlite3

K_FACTOR = 32  # the most a rating can move in one match
NICKNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{2,20}$")


class LadderError(Exception):
    """The match or request breaks a ladder rule (HTTP 400)."""


def expected_score(team_rating, opponent_rating):
    """Chance (0 to 1) that a team beats the opponent, from the Elo formula."""
    return 1 / (1 + 10 ** ((opponent_rating - team_rating) / 400))


def rating_change(team_a_rating, team_b_rating, team_a_won):
    """Points team A gains (or loses, if negative). Team B moves the opposite way."""
    actual = 1 if team_a_won else 0
    return round(K_FACTOR * (actual - expected_score(team_a_rating, team_b_rating)))


def join_ladder(conn, user_id, nickname):
    """Add a member to the ladder under a nickname. Joining twice does nothing."""
    existing = get_player(conn, user_id)
    if existing is not None:
        return existing
    if not isinstance(nickname, str) or not NICKNAME_PATTERN.match(nickname):
        raise LadderError("nickname must be 2-20 letters, digits or underscores")

    try:
        conn.execute(
            "INSERT INTO players (user_id, nickname) VALUES (?, ?)", (user_id, nickname)
        )
    except sqlite3.IntegrityError:
        raise LadderError("nickname is already taken")
    conn.commit()
    return get_player(conn, user_id)


def get_player(conn, user_id):
    row = conn.execute(
        "SELECT user_id, nickname, rating, matches_played FROM players WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def record_match(conn, recorded_by, team_a, team_b, winner):
    """Save a doubles match and update all four players' ratings.

    team_a and team_b are lists of two user ids; winner is "A" or "B".
    """
    if not (isinstance(team_a, list) and isinstance(team_b, list)
            and len(team_a) == 2 and len(team_b) == 2):
        raise LadderError("each team must be a list of two player ids")
    all_players = team_a + team_b
    if not all(isinstance(user_id, int) for user_id in all_players):
        raise LadderError("player ids must be whole numbers")
    if len(set(all_players)) != 4:
        raise LadderError("a match needs four different players")
    if winner not in ("A", "B"):
        raise LadderError('winner must be "A" or "B"')
    if recorded_by not in all_players:
        raise LadderError("only a player in the match can record it")

    players = {user_id: get_player(conn, user_id) for user_id in all_players}
    missing = [user_id for user_id, player in players.items() if player is None]
    if missing:
        raise LadderError(f"players {missing} have not joined the ladder")

    team_a_rating = (players[team_a[0]]["rating"] + players[team_a[1]]["rating"]) / 2
    team_b_rating = (players[team_b[0]]["rating"] + players[team_b[1]]["rating"]) / 2
    change = rating_change(team_a_rating, team_b_rating, winner == "A")

    for user_id in team_a:
        _apply_result(conn, user_id, change)
    for user_id in team_b:
        _apply_result(conn, user_id, -change)

    cursor = conn.execute(
        "INSERT INTO matches (team_a_p1, team_a_p2, team_b_p1, team_b_p2, winner, recorded_by) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (*team_a, *team_b, winner, recorded_by),
    )
    conn.commit()
    return {"id": cursor.lastrowid, "winner": winner, "team_a_change": change, "team_b_change": -change}


def _apply_result(conn, user_id, change):
    conn.execute(
        "UPDATE players SET rating = rating + ?, matches_played = matches_played + 1 "
        "WHERE user_id = ?",
        (change, user_id),
    )


def leaderboard(conn):
    """All players, best rating first, numbered from rank 1.

    Ties go to whoever has played more matches.
    """
    rows = conn.execute(
        "SELECT user_id, nickname, rating, matches_played FROM players "
        "ORDER BY rating DESC, matches_played DESC, user_id"
    ).fetchall()
    return [{"rank": rank, **dict(row)} for rank, row in enumerate(rows, start=1)]
