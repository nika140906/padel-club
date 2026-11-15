import pytest

from tests.conftest import log_in_as


def join_as(client, user_id, nickname):
    """Log in as this member, join the ladder under the nickname, return their id."""
    log_in_as(client, user_id)
    return client.post("/ladder/join", json={"nickname": nickname}).get_json()["user_id"]


@pytest.fixture
def four_members(client):
    """Four members on the ladder; the last one (dan) stays logged in."""
    names = ("alice", "bob", "carol", "dan")
    ids = [join_as(client, user_id, name) for user_id, name in enumerate(names, start=1)]
    return client, ids


@pytest.mark.parametrize("method, url", [
    ("post", "/ladder/join"),
    ("get", "/ladder/me"),
    ("post", "/ladder/matches"),
    ("get", "/ladder/leaderboard"),
])
def test_ladder_routes_require_login(client, method, url):
    assert getattr(client, method)(url).status_code == 401


def test_join_returns_new_player(logged_in_client):
    response = logged_in_client.post("/ladder/join", json={"nickname": "nika"})

    assert response.status_code == 201
    assert response.get_json()["rating"] == 1000


def test_join_with_bad_nickname_returns_400(logged_in_client):
    response = logged_in_client.post("/ladder/join", json={"nickname": "a"})

    assert response.status_code == 400


def test_me_before_joining_returns_404(logged_in_client):
    assert logged_in_client.get("/ladder/me").status_code == 404


def test_me_after_joining(logged_in_client):
    logged_in_client.post("/ladder/join", json={"nickname": "nika"})

    assert logged_in_client.get("/ladder/me").get_json()["nickname"] == "nika"


def test_record_match_updates_leaderboard(four_members):
    client, (alice, bob, carol, dan) = four_members

    response = client.post(
        "/ladder/matches",
        json={"team_a": [alice, bob], "team_b": [carol, dan], "winner": "B"},
    )

    assert response.status_code == 201
    board = client.get("/ladder/leaderboard").get_json()["leaderboard"]
    assert [p["nickname"] for p in board[:2]] == ["carol", "dan"]
    assert board[0]["rating"] == 1016


def test_record_match_with_bad_data_returns_400(four_members):
    client, (alice, bob, carol, dan) = four_members

    response = client.post(
        "/ladder/matches",
        json={"team_a": [alice, bob], "team_b": [carol, dan], "winner": "draw"},
    )

    assert response.status_code == 400


def test_member_not_in_the_match_cannot_record_it(four_members):
    client, (alice, bob, carol, dan) = four_members
    join_as(client, 5, "erin")  # erin is now logged in

    response = client.post(
        "/ladder/matches",
        json={"team_a": [alice, bob], "team_b": [carol, dan], "winner": "A"},
    )

    assert response.status_code == 400
    assert "only a player" in response.get_json()["error"]


def test_fake_token_returns_401(client):
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer not-a-real-token"

    assert client.get("/ladder/leaderboard").status_code == 401
