import logging

from flask import Blueprint, current_app, request

from padel.auth.decorators import current_user_id, login_required
from padel.bookings_client import BookingsUnavailable, get_member
from padel.db import get_db
from padel.ladder.service import LadderError, get_player, join_ladder, leaderboard, record_match

log = logging.getLogger(__name__)

bp = Blueprint("ladder", __name__, url_prefix="/ladder")


@bp.post("/join")
@login_required
def join():
    """Join the ladder. This is the one request that needs the other service.

    The ladder asks bookings for the member's account. Without a nickname,
    the member joins under their username. If bookings is down or too slow,
    the member gets a clear 503 and can try again; the rest of the ladder
    keeps working.
    """
    data = request.get_json(silent=True) or {}
    try:
        member = get_member(
            current_app.config["BOOKINGS_URL"],
            request.headers["Authorization"],
            current_app.config["BOOKINGS_TIMEOUT_S"],
        )
    except BookingsUnavailable as error:
        log.warning("join: bookings service unavailable: %s", error)
        return {"error": "the bookings service is not responding, so you cannot join "
                         "the ladder right now; please try again in a minute"}, 503
    if member is None:
        return {"error": "your member account was not found"}, 404

    try:
        player = join_ladder(get_db(), current_user_id(), data.get("nickname") or member["username"])
    except LadderError as error:
        return {"error": str(error)}, 400
    return player, 201


@bp.get("/me")
@login_required
def me():
    player = get_player(get_db(), current_user_id())
    if player is None:
        return {"error": "you have not joined the ladder"}, 404
    return player


@bp.post("/matches")
@login_required
def add_match():
    data = request.get_json(silent=True) or {}
    try:
        result = record_match(
            get_db(),
            current_user_id(),
            data.get("team_a"),
            data.get("team_b"),
            data.get("winner"),
        )
    except LadderError as error:
        return {"error": str(error)}, 400
    return result, 201


@bp.get("/leaderboard")
@login_required
def show_leaderboard():
    return {"leaderboard": leaderboard(get_db())}
