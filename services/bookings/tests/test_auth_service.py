import pytest

from padel.auth.service import AuthError, authenticate, get_username, register_user


def test_register_returns_new_user_id(conn):
    user_id = register_user(conn, "nika", "secret123")

    assert get_username(conn, user_id) == "nika"


def test_password_is_stored_hashed_not_plain(conn):
    register_user(conn, "nika", "secret123")

    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]

    assert stored != "secret123"


def test_register_rejects_duplicate_username(conn):
    register_user(conn, "nika", "secret123")

    with pytest.raises(AuthError, match="already taken"):
        register_user(conn, "nika", "another123")


@pytest.mark.parametrize("username", ["ab", "has space", "x" * 31, None, 123])
def test_register_rejects_invalid_username(conn, username):
    with pytest.raises(AuthError, match="username"):
        register_user(conn, username, "secret123")


@pytest.mark.parametrize("password", ["short", "", None])
def test_register_rejects_invalid_password(conn, password):
    with pytest.raises(AuthError, match="password"):
        register_user(conn, "nika", password)


def test_authenticate_returns_user_id_for_correct_password(conn):
    user_id = register_user(conn, "nika", "secret123")

    assert authenticate(conn, "nika", "secret123") == user_id


def test_authenticate_rejects_wrong_password(conn):
    register_user(conn, "nika", "secret123")

    with pytest.raises(AuthError, match="invalid username or password"):
        authenticate(conn, "nika", "wrong-password")


def test_authenticate_rejects_unknown_user(conn):
    with pytest.raises(AuthError, match="invalid username or password"):
        authenticate(conn, "nobody", "secret123")


def test_get_username_of_unknown_user_is_none(conn):
    assert get_username(conn, 999) is None
