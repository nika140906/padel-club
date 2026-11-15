from flask import Blueprint, request

from padel.auth.decorators import current_user_id, login_required
from padel.bookings.service import (
    BookingConflict,
    BookingError,
    BookingNotFound,
    cancel_booking,
    create_booking,
    list_court_bookings_on_day,
    list_courts,
    list_user_bookings,
)
from padel.db import get_db

bp = Blueprint("bookings", __name__)


def error_response(error):
    """Turn a booking error into a JSON response with the right status code."""
    if isinstance(error, BookingNotFound):
        status = 404
    elif isinstance(error, BookingConflict):
        status = 409
    else:
        status = 400
    return {"error": str(error)}, status


@bp.get("/courts")
@login_required
def courts():
    return {"courts": list_courts(get_db())}


@bp.get("/courts/<int:court_id>/bookings")
@login_required
def court_schedule(court_id):
    try:
        bookings = list_court_bookings_on_day(get_db(), court_id, request.args.get("day"))
    except BookingError as error:
        return error_response(error)
    return {"bookings": bookings}


@bp.post("/bookings")
@login_required
def book_court():
    data = request.get_json(silent=True) or {}
    try:
        booking = create_booking(
            get_db(),
            current_user_id(),
            data.get("court_id"),
            data.get("start_time"),
            data.get("duration_minutes"),
        )
    except BookingError as error:
        return error_response(error)
    return booking, 201


@bp.get("/bookings/mine")
@login_required
def my_bookings():
    return {"bookings": list_user_bookings(get_db(), current_user_id())}


@bp.delete("/bookings/<int:booking_id>")
@login_required
def cancel(booking_id):
    try:
        cancel_booking(get_db(), booking_id, current_user_id())
    except BookingError as error:
        return error_response(error)
    return {"status": "cancelled"}
