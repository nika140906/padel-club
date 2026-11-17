import time

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


# Joining needs the bookings service (here the stub from conftest.py).

def test_join_sends_the_members_own_token_to_bookings(logged_in_client, bookings_stub):
    logged_in_client.post("/ladder/join", json={"nickname": "nika"})

    assert bookings_stub.received_auth == [logged_in_client.environ_base["HTTP_AUTHORIZATION"]]


def test_join_without_nickname_uses_username_from_bookings(logged_in_client):
    response = logged_in_client.post("/ladder/join", json={})

    assert response.status_code == 201
    assert response.get_json()["nickname"] == "member1"


def test_join_when_account_is_gone_returns_404(logged_in_client, bookings_stub):
    bookings_stub.mode = "missing"

    response = logged_in_client.post("/ladder/join", json={"nickname": "nika"})

    assert response.status_code == 404
    assert logged_in_client.get("/ladder/me").status_code == 404  # nobody was added


@pytest.mark.parametrize("mode", ["broken", "not_json"])
def test_join_when_bookings_misbehaves_returns_503(logged_in_client, bookings_stub, mode):
    bookings_stub.mode = mode

    response = logged_in_client.post("/ladder/join", json={"nickname": "nika"})

    assert response.status_code == 503
    assert "try again" in response.get_json()["error"]


def test_join_when_bookings_is_down_returns_503(logged_in_client, bookings_stub):
    bookings_stub.stop()  # nothing listens on that port any more

    response = logged_in_client.post("/ladder/join", json={"nickname": "nika"})

    assert response.status_code == 503


def test_join_when_bookings_is_too_slow_gives_up_after_the_timeout(logged_in_client, bookings_stub):
    bookings_stub.mode = "slow"  # answers after 1 second
    logged_in_client.application.config["BOOKINGS_TIMEOUT_S"] = 0.2

    started = time.perf_counter()
    response = logged_in_client.post("/ladder/join", json={"nickname": "nika"})

    assert response.status_code == 503
    assert time.perf_counter() - started < 0.9


def test_rest_of_the_ladder_works_while_bookings_is_down(four_members, bookings_stub):
    client, (alice, bob, carol, dan) = four_members
    bookings_stub.stop()

    assert client.get("/ladder/leaderboard").status_code == 200
    assert client.get("/ladder/me").status_code == 200
    response = client.post(
        "/ladder/matches",
        json={"team_a": [alice, bob], "team_b": [carol, dan], "winner": "A"},
    )
    assert response.status_code == 201
