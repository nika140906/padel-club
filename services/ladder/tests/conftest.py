import pytest

from app import create_app
from padel.auth.tokens import make_token
from padel.db import connect, get_db_path, init_db

TEST_SECRET = "test-secret"


@pytest.fixture
def conn(tmp_path):
    """A connection to a fresh database with all tables created."""
    path = get_db_path(str(tmp_path))
    init_db(path)
    connection = connect(path)
    yield connection
    connection.close()


@pytest.fixture
def client(tmp_path):
    """A test client for an app that uses a fresh database."""
    return create_app(data_dir=str(tmp_path), token_secret=TEST_SECRET).test_client()


def log_in_as(client, user_id):
    """Send a token for this user on every later request.

    The ladder has no login route: in the real system the token comes from
    the bookings service, signed with the same secret. Here the test makes
    the same token directly.
    """
    token = make_token(TEST_SECRET, user_id)
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"


@pytest.fixture
def logged_in_client(client):
    """A test client where member 1 is logged in."""
    log_in_as(client, 1)
    return client
