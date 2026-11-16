import re

import pymssql
from werkzeug.security import check_password_hash, generate_password_hash

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")
MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """Raised when registration or login fails."""


def register_user(conn, username, password):
    """Create a user with a hashed password and return the new user's id."""
    if not isinstance(username, str) or not USERNAME_PATTERN.match(username):
        raise AuthError("username must be 3-30 letters, digits or underscores")
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

    try:
        # OUTPUT INSERTED.id hands back the id SQL Server gave the new row.
        row = conn.execute(
            "INSERT INTO users (username, password_hash) OUTPUT INSERTED.id VALUES (%s, %s)",
            (username, generate_password_hash(password)),
        ).fetchone()
    except pymssql.IntegrityError:  # the UNIQUE rule on username
        conn.rollback()
        raise AuthError("username is already taken")
    conn.commit()
    return row["id"]


def authenticate(conn, username, password):
    """Return the user's id if the username and password match."""
    # A number or list as username would make SQL Server try to convert
    # every stored username, so anything that is not text is rejected first.
    if not isinstance(username, str):
        raise AuthError("invalid username or password")
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = %s", (username,)
    ).fetchone()
    # Same message for unknown user and wrong password, so an attacker
    # cannot find out which usernames exist.
    if row is None or not check_password_hash(row["password_hash"], str(password)):
        raise AuthError("invalid username or password")
    return row["id"]


def get_username(conn, user_id):
    row = conn.execute("SELECT username FROM users WHERE id = %s", (user_id,)).fetchone()
    return row["username"] if row else None
