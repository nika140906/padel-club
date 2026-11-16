from datetime import datetime, timedelta

# Club rules.
OPENING_HOUR = 8
CLOSING_HOUR = 23
ALLOWED_DURATIONS = (60, 90)  # minutes
TIME_FORMAT = "%Y-%m-%d %H:%M"


class BookingError(Exception):
    """The request breaks a booking rule (HTTP 400)."""


class BookingNotFound(BookingError):
    """The court or booking does not exist (HTTP 404)."""


class BookingConflict(BookingError):
    """The court is already booked at that time (HTTP 409)."""


def parse_time(text):
    try:
        return datetime.strptime(text, TIME_FORMAT)
    except (TypeError, ValueError):
        raise BookingError('time must look like "2026-10-01 18:00"')


def booking_from_row(row):
    """Turn a database row into the JSON shape of a booking.

    SQL Server returns times as datetime objects; the API keeps sending
    them as text like "2026-10-01 18:00", the same as before.
    """
    return {
        "id": row["id"],
        "court_id": row["court_id"],
        "user_id": row["user_id"],
        "start_time": row["start_time"].strftime(TIME_FORMAT),
        "end_time": row["end_time"].strftime(TIME_FORMAT),
    }


def list_courts(conn):
    rows = conn.execute("SELECT id, name FROM courts ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def create_booking(conn, user_id, court_id, start_time, duration_minutes, now=None):
    """Book a court for a user and return the new booking."""
    now = now or datetime.now()
    start = parse_time(start_time)

    if duration_minutes not in ALLOWED_DURATIONS:
        raise BookingError("duration must be 60 or 90 minutes")
    end = start + timedelta(minutes=duration_minutes)

    if start.minute not in (0, 30):
        raise BookingError("bookings start on the hour or half hour")
    if start < now:
        raise BookingError("cannot book in the past")
    closing = start.replace(hour=CLOSING_HOUR, minute=0)
    if start.hour < OPENING_HOUR or end > closing:
        raise BookingError(f"the club is open {OPENING_HOUR}:00-{CLOSING_HOUR}:00")

    # A text or list id would make SQL Server fail to convert it, so check the type first.
    if not isinstance(court_id, int) or isinstance(court_id, bool):
        raise BookingError("court_id must be a whole number")
    court = conn.execute("SELECT id FROM courts WHERE id = %s", (court_id,)).fetchone()
    if court is None:
        raise BookingNotFound("court not found")

    # Two bookings overlap when each one starts before the other ends.
    clash = conn.execute(
        "SELECT id FROM bookings WHERE court_id = %s AND start_time < %s AND end_time > %s",
        (court_id, end, start),
    ).fetchone()
    if clash is not None:
        raise BookingConflict("court is already booked at that time")

    row = conn.execute(
        "INSERT INTO bookings (court_id, user_id, start_time, end_time) "
        "OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)",
        (court_id, user_id, start, end),
    ).fetchone()
    conn.commit()
    return get_booking(conn, row["id"])


def get_booking(conn, booking_id):
    row = conn.execute(
        "SELECT id, court_id, user_id, start_time, end_time FROM bookings WHERE id = %s",
        (booking_id,),
    ).fetchone()
    return booking_from_row(row) if row else None


def cancel_booking(conn, booking_id, user_id):
    """Delete a booking, but only if it belongs to this user."""
    booking = get_booking(conn, booking_id)
    # Someone else's booking is reported as "not found", so users cannot
    # discover other people's bookings by guessing ids.
    if booking is None or booking["user_id"] != user_id:
        raise BookingNotFound("booking not found")
    conn.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
    conn.commit()


def list_user_bookings(conn, user_id):
    rows = conn.execute(
        "SELECT id, court_id, user_id, start_time, end_time FROM bookings "
        "WHERE user_id = %s ORDER BY start_time",
        (user_id,),
    ).fetchall()
    return [booking_from_row(row) for row in rows]


def list_court_bookings_on_day(conn, court_id, day):
    """All bookings for one court on one day ("2026-10-01"), earliest first."""
    try:
        first = datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise BookingError('day must look like "2026-10-01"')
    next_day = first + timedelta(days=1)
    rows = conn.execute(
        "SELECT id, court_id, user_id, start_time, end_time FROM bookings "
        "WHERE court_id = %s AND start_time >= %s AND start_time < %s ORDER BY start_time",
        (court_id, first, next_day),
    ).fetchall()
    return [booking_from_row(row) for row in rows]
