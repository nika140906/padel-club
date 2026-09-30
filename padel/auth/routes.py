from flask import Blueprint, request, session

from padel.auth.decorators import current_user_id, login_required
from padel.auth.service import AuthError, authenticate, get_username, register_user
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
    data = request.get_json(silent=True) or {}
    try:
        user_id = authenticate(get_db(), data.get("username"), data.get("password"))
    except AuthError as error:
        return {"error": str(error)}, 401
    session.clear()
    session["user_id"] = user_id
    return {"id": user_id, "username": data["username"]}


@bp.post("/logout")
def logout():
    session.clear()
    return {"status": "logged out"}


@bp.get("/me")
@login_required
def me():
    user_id = current_user_id()
    return {"id": user_id, "username": get_username(get_db(), user_id)}
