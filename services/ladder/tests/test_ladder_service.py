import pytest

from padel.ladder.service import (
    LadderError,
    expected_score,
    get_player,
    join_ladder,
    leaderboard,
    rating_change,
    record_match,
)


@pytest.fixture
def four_players(conn):
    for user_id in (1, 2, 3, 4):
        join_ladder(conn, user_id, f"player{user_id}")
    return conn


# --- Elo maths -------------------------------------------------------------

def test_equal_teams_each_have_a_fifty_percent_chance():
    assert expected_score(1000, 1000) == 0.5


def test_stronger_team_is_expected_to_win():
    assert expected_score(1200, 1000) > 0.5
    assert expected_score(1000, 1200) < 0.5


def test_win_between_equal_teams_is_worth_half_of_k():
    assert rating_change(1000, 1000, team_a_won=True) == 16
    assert rating_change(1000, 1000, team_a_won=False) == -16


def test_upset_win_is_worth_more_than_expected_win():
    underdog_wins = rating_change(1000, 1200, team_a_won=True)
    favourite_wins = rating_change(1200, 1000, team_a_won=True)

    assert underdog_wins > favourite_wins > 0


# --- Joining ---------------------------------------------------------------

def test_new_player_starts_at_1000_with_no_matches(conn):
    player = join_ladder(conn, 1, "nika")

    assert player == {"user_id": 1, "nickname": "nika", "rating": 1000, "matches_played": 0}


def test_joining_twice_keeps_the_first_nickname(conn):
    join_ladder(conn, 1, "nika")
    player = join_ladder(conn, 1, "other_name")

    assert player["nickname"] == "nika"
    assert len(leaderboard(conn)) == 1


def test_nickname_must_be_unique(conn):
    join_ladder(conn, 1, "nika")

    with pytest.raises(LadderError, match="already taken"):
        join_ladder(conn, 2, "nika")


@pytest.mark.parametrize("nickname", ["a", "x" * 21, "has space", None, 7])
def test_invalid_nickname_is_rejected(conn, nickname):
    with pytest.raises(LadderError, match="nickname must be"):
        join_ladder(conn, 1, nickname)


def test_get_unknown_player_is_none(conn):
    assert get_player(conn, 99) is None


# --- Recording matches -----------------------------------------------------

def test_winners_gain_and_losers_lose_the_same_points(four_players):
    result = record_match(four_players, 1, [1, 2], [3, 4], "A")

    assert result["team_a_change"] == 16
    assert result["team_b_change"] == -16
    ratings = {p["user_id"]: p["rating"] for p in leaderboard(four_players)}
    assert ratings == {1: 1016, 2: 1016, 3: 984, 4: 984}


def test_team_b_can_win(four_players):
    record_match(four_players, 3, [1, 2], [3, 4], "B")

    assert get_player(four_players, 3)["rating"] == 1016
    assert get_player(four_players, 1)["rating"] == 984


def test_recording_a_match_counts_it_for_all_four_players(four_players):
    record_match(four_players, 1, [1, 2], [3, 4], "A")

    assert all(p["matches_played"] == 1 for p in leaderboard(four_players))


def test_match_is_saved(four_players):
    result = record_match(four_players, 1, [1, 2], [3, 4], "A")

    row = four_players.execute("SELECT * FROM matches WHERE id = ?", (result["id"],)).fetchone()
    assert (row["team_a_p1"], row["team_b_p2"], row["winner"]) == (1, 4, "A")


@pytest.mark.parametrize("team_a, team_b, message", [
    ([1], [3, 4], "two player ids"),
    ([1, 2, 3], [3, 4], "two player ids"),
    ("1,2", [3, 4], "two player ids"),
    ([1, "2"], [3, 4], "whole numbers"),
    ([1, 2], [2, 3], "four different players"),
])
def test_invalid_teams_are_rejected(four_players, team_a, team_b, message):
    with pytest.raises(LadderError, match=message):
        record_match(four_players, 1, team_a, team_b, "A")


def test_winner_must_be_a_or_b(four_players):
    with pytest.raises(LadderError, match="winner"):
        record_match(four_players, 1, [1, 2], [3, 4], "draw")


def test_only_a_player_in_the_match_can_record_it(four_players):
    with pytest.raises(LadderError, match="only a player"):
        record_match(four_players, 99, [1, 2], [3, 4], "A")


def test_players_must_have_joined_the_ladder(conn):
    join_ladder(conn, 1, "player1")
    join_ladder(conn, 2, "player2")

    with pytest.raises(LadderError, match=r"\[3, 4\] have not joined"):
        record_match(conn, 1, [1, 2], [3, 4], "A")


def test_rejected_match_changes_nothing(four_players):
    with pytest.raises(LadderError):
        record_match(four_players, 1, [1, 2], [3, 4], "draw")

    assert all(p["rating"] == 1000 for p in leaderboard(four_players))


# --- Leaderboard -----------------------------------------------------------

def test_leaderboard_is_sorted_by_rating(four_players):
    record_match(four_players, 1, [1, 2], [3, 4], "A")
    join_ladder(four_players, 5, "newcomer")  # 1000 points, no matches

    board = leaderboard(four_players)

    assert [p["user_id"] for p in board] == [1, 2, 5, 3, 4]
    assert [p["rank"] for p in board] == [1, 2, 3, 4, 5]
    assert board[2]["nickname"] == "newcomer"
