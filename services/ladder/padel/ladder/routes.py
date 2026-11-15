from flask import Blueprint, request

from padel.auth.decorators import current_user_id, login_required
from padel.db import get_db
from padel.ladder.service import LadderError, get_player, join_ladder, leaderboard, record_match

bp = Blueprint("ladder", __name__, url_prefix="/ladder")


@bp.post("/join")
@login_required
def join():
    data = request.get_json(silent=True) or {}
    try:
        player = join_ladder(get_db(), current_user_id(), data.get("nickname"))
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
