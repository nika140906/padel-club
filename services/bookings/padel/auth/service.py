import re
import sqlite3

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
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
    except sqlite3.IntegrityError:
        raise AuthError("username is already taken")
    conn.commit()
    return cursor.lastrowid


def authenticate(conn, username, password):
    """Return the user's id if the username and password match."""
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    # Same message for unknown user and wrong password, so an attacker
    # cannot find out which usernames exist.
    if row is None or not check_password_hash(row["password_hash"], str(password)):
        raise AuthError("invalid username or password")
    return row["id"]


def get_username(conn, user_id):
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["username"] if row else None
