from datetime import datetime

import pytest

from padel.bookings.service import (
    BookingConflict,
    BookingError,
    BookingNotFound,
    cancel_booking,
    create_booking,
    get_booking,
    list_court_bookings_on_day,
    list_courts,
    list_user_bookings,
)

# A fixed "now" so the tests do not depend on today's date.
NOW = datetime(2026, 10, 1, 9, 0)
ALICE = 1
BOB = 2


def book(conn, start="2026-10-01 18:00", duration=90, user_id=ALICE, court_id=1):
    return create_booking(conn, user_id, court_id, start, duration, now=NOW)


def test_list_courts_returns_the_four_seeded_courts(conn):
    names = [court["name"] for court in list_courts(conn)]

    assert names == ["Court 1", "Court 2", "Court 3", "Court 4"]


def test_create_booking_calculates_end_time(conn):
    booking = book(conn, start="2026-10-01 18:00", duration=90)

    assert booking["start_time"] == "2026-10-01 18:00"
    assert booking["end_time"] == "2026-10-01 19:30"
    assert booking["user_id"] == ALICE


@pytest.mark.parametrize("start", ["tomorrow at six", "2026-10-01", None])
def test_create_booking_rejects_badly_formatted_time(conn, start):
    with pytest.raises(BookingError, match="time must look like"):
        book(conn, start=start)


@pytest.mark.parametrize("duration", [30, 45, 120, "90"])
def test_create_booking_rejects_other_durations(conn, duration):
    with pytest.raises(BookingError, match="60 or 90"):
        book(conn, duration=duration)


def test_create_booking_rejects_odd_start_minutes(conn):
    with pytest.raises(BookingError, match="hour or half hour"):
        book(conn, start="2026-10-01 18:15")


def test_create_booking_rejects_the_past(conn):
    with pytest.raises(BookingError, match="past"):
        book(conn, start="2026-10-01 08:00")  # NOW is 09:00


@pytest.mark.parametrize("start, duration", [
    ("2026-10-02 07:30", 60),  # starts before opening
    ("2026-10-02 22:00", 90),  # ends 23:30, after closing
])
def test_create_booking_rejects_outside_opening_hours(conn, start, duration):
    with pytest.raises(BookingError, match="open"):
        book(conn, start=start, duration=duration)


def test_booking_may_end_exactly_at_closing(conn):
    booking = book(conn, start="2026-10-01 21:30", duration=90)

    assert booking["end_time"] == "2026-10-01 23:00"


def test_create_booking_rejects_unknown_court(conn):
    with pytest.raises(BookingNotFound, match="court"):
        book(conn, court_id=99)


@pytest.mark.parametrize("start", [
    "2026-10-01 18:00",  # same time
    "2026-10-01 17:00",  # ends inside the existing booking
    "2026-10-01 19:00",  # starts inside the existing booking
])
def test_overlapping_booking_on_same_court_is_rejected(conn, start):
    book(conn, start="2026-10-01 18:00", duration=90)  # 18:00-19:30

    with pytest.raises(BookingConflict):
        book(conn, start=start, duration=90, user_id=BOB)


def test_back_to_back_bookings_are_allowed(conn):
    book(conn, start="2026-10-01 18:00", duration=90)  # ends 19:30

    booking = book(conn, start="2026-10-01 19:30", duration=60, user_id=BOB)

    assert booking["start_time"] == "2026-10-01 19:30"


def test_same_time_on_a_different_court_is_allowed(conn):
    book(conn, court_id=1)

    booking = book(conn, court_id=2, user_id=BOB)

    assert booking["court_id"] == 2


def test_cancel_own_booking_removes_it(conn):
    booking = book(conn)

    cancel_booking(conn, booking["id"], ALICE)

    assert get_booking(conn, booking["id"]) is None


def test_cannot_cancel_someone_elses_booking(conn):
    booking = book(conn, user_id=ALICE)

    with pytest.raises(BookingNotFound):
        cancel_booking(conn, booking["id"], BOB)
    assert get_booking(conn, booking["id"]) is not None


def test_cancel_unknown_booking_raises_not_found(conn):
    with pytest.raises(BookingNotFound):
        cancel_booking(conn, 999, ALICE)


def test_list_user_bookings_returns_only_that_users_bookings_in_order(conn):
    book(conn, start="2026-10-02 20:00", user_id=ALICE)
    book(conn, start="2026-10-01 18:00", user_id=ALICE)
    book(conn, start="2026-10-01 10:00", user_id=BOB)

    starts = [b["start_time"] for b in list_user_bookings(conn, ALICE)]

    assert starts == ["2026-10-01 18:00", "2026-10-02 20:00"]


def test_list_court_bookings_on_day_only_returns_that_day_and_court(conn):
    book(conn, start="2026-10-01 18:00", court_id=1)
    book(conn, start="2026-10-01 10:00", court_id=1)
    book(conn, start="2026-10-02 18:00", court_id=1)  # other day
    book(conn, start="2026-10-01 18:00", court_id=2)  # other court

    starts = [b["start_time"] for b in list_court_bookings_on_day(conn, 1, "2026-10-01")]

    assert starts == ["2026-10-01 10:00", "2026-10-01 18:00"]


def test_list_court_bookings_rejects_bad_day(conn):
    with pytest.raises(BookingError, match="day must look like"):
        list_court_bookings_on_day(conn, 1, "01/10/2026")
