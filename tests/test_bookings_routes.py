import pytest

from tests.conftest import log_in_as

# A date far in the future, so these tests never fail as "in the past".
DAY = "2030-06-01"


def book(client, start=f"{DAY} 18:00", duration=90, court_id=1):
    return client.post(
        "/bookings",
        json={"court_id": court_id, "start_time": start, "duration_minutes": duration},
    )


@pytest.mark.parametrize("method, url", [
    ("get", "/courts"),
    ("get", f"/courts/1/bookings?day={DAY}"),
    ("post", "/bookings"),
    ("get", "/bookings/mine"),
    ("delete", "/bookings/1"),
])
def test_booking_routes_require_login(client, method, url):
    response = getattr(client, method)(url)

    assert response.status_code == 401


def test_list_courts(logged_in_client):
    response = logged_in_client.get("/courts")

    assert response.status_code == 200
    assert len(response.get_json()["courts"]) == 4


def test_book_a_court_returns_201(logged_in_client):
    response = book(logged_in_client)

    assert response.status_code == 201
    assert response.get_json()["end_time"] == f"{DAY} 19:30"


def test_rule_break_returns_400(logged_in_client):
    response = book(logged_in_client, duration=45)

    assert response.status_code == 400
    assert "60 or 90" in response.get_json()["error"]


def test_unknown_court_returns_404(logged_in_client):
    response = book(logged_in_client, court_id=99)

    assert response.status_code == 404


def test_double_booking_returns_409(logged_in_client):
    book(logged_in_client)

    response = book(logged_in_client)

    assert response.status_code == 409


def test_post_without_json_body_returns_400(logged_in_client):
    response = logged_in_client.post("/bookings", data="not json")

    assert response.status_code == 400


def test_my_bookings_lists_what_i_booked(logged_in_client):
    book(logged_in_client)

    bookings = logged_in_client.get("/bookings/mine").get_json()["bookings"]

    assert [b["start_time"] for b in bookings] == [f"{DAY} 18:00"]


def test_court_schedule_for_a_day(logged_in_client):
    book(logged_in_client, start=f"{DAY} 10:00")
    book(logged_in_client, start=f"{DAY} 18:00")

    response = logged_in_client.get(f"/courts/1/bookings?day={DAY}")

    assert [b["start_time"] for b in response.get_json()["bookings"]] == [
        f"{DAY} 10:00",
        f"{DAY} 18:00",
    ]


def test_court_schedule_without_day_returns_400(logged_in_client):
    response = logged_in_client.get("/courts/1/bookings")

    assert response.status_code == 400


def test_cancel_own_booking(logged_in_client):
    booking_id = book(logged_in_client).get_json()["id"]

    response = logged_in_client.delete(f"/bookings/{booking_id}")

    assert response.status_code == 200
    assert logged_in_client.get("/bookings/mine").get_json()["bookings"] == []


def test_cannot_cancel_another_members_booking(logged_in_client):
    booking_id = book(logged_in_client).get_json()["id"]
    logged_in_client.post("/auth/logout")
    log_in_as(logged_in_client, "someone_else")

    response = logged_in_client.delete(f"/bookings/{booking_id}")

    assert response.status_code == 404
