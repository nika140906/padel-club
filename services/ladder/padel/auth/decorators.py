from functools import wraps

from flask import current_app, g, request

from padel.auth.tokens import read_token


def login_required(view):
    """Reject the request with 401 unless it carries a valid login token."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = user_id_from_request()
        if user_id is None:
            return {"error": "login required"}, 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def user_id_from_request():
    """Read "Authorization: Bearer <token>" and return the user id, or None."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme != "Bearer" or not token:
        return None
    return read_token(current_app.config["TOKEN_SECRET"], token)


def current_user_id():
    return g.user_id
