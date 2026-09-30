from functools import wraps

from flask import session


def login_required(view):
    """Reject the request with 401 unless a user is logged in."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return {"error": "login required"}, 401
        return view(*args, **kwargs)

    return wrapped


def current_user_id():
    return session["user_id"]
