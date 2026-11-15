from flask import Blueprint, current_app, request

from padel.auth.decorators import current_user_id, login_required
from padel.auth.service import AuthError, authenticate, get_username, register_user
from padel.auth.tokens import make_token
from padel.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    try:
        user_id = register_user(get_db(), data.get("username"), data.get("password"))
    except AuthError as error:
        return {"error": str(error)}, 400
    return {"id": user_id, "username": data["username"]}, 201


@bp.post("/login")
def login():
    """Check the password and hand back a token for the Authorization header.

    There is no logout route: tokens are not stored on the server, so the
    UI logs out by forgetting its token.
    """
    data = request.get_json(silent=True) or {}
    try:
        user_id = authenticate(get_db(), data.get("username"), data.get("password"))
    except AuthError as error:
        return {"error": str(error)}, 401
    token = make_token(current_app.config["TOKEN_SECRET"], user_id)
    return {"id": user_id, "username": data["username"], "token": token}


@bp.get("/me")
@login_required
def me():
    user_id = current_user_id()
    return {"id": user_id, "username": get_username(get_db(), user_id)}
