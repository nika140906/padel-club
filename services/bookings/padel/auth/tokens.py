"""Signed login tokens, shared by both services.

The bookings service makes a token when a member logs in. The browser sends
it back on every request in the header "Authorization: Bearer <token>".
Both services check it with the same TOKEN_SECRET, so the ladder can tell
who is logged in without calling the bookings service.

A token is the user id plus a timestamp, signed with the secret. Anyone can
read the user id inside it, but nobody can change it or make a new token
without the secret. This file is the same in both services.
"""
from itsdangerous import BadSignature, URLSafeTimedSerializer

TOKEN_MAX_AGE_SECONDS = 12 * 60 * 60  # members log in again after 12 hours
SALT = "padel-login"  # keeps these tokens apart from anything else signed with the secret


def make_token(secret, user_id):
    return URLSafeTimedSerializer(secret, salt=SALT).dumps({"user_id": user_id})


def read_token(secret, token, max_age=TOKEN_MAX_AGE_SECONDS):
    """Return the user id inside the token, or None if it is fake or too old."""
    try:
        data = URLSafeTimedSerializer(secret, salt=SALT).loads(token, max_age=max_age)
    except BadSignature:  # also covers SignatureExpired
        return None
    return data.get("user_id")
