import pytest

from app import create_app
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


def use_token(client, token):
    """Send this token on every later request from the client, like the UI does."""
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"


def log_out(client):
    client.environ_base.pop("HTTP_AUTHORIZATION", None)


def log_in_as(client, username, password="secret123"):
    """Register a user, log them in and use their token on this client."""
    client.post("/auth/register", json={"username": username, "password": password})
    response = client.post("/auth/login", json={"username": username, "password": password})
    use_token(client, response.get_json()["token"])


@pytest.fixture
def logged_in_client(client):
    """A test client where the user "nika" is logged in."""
    log_in_as(client, "nika")
    return client
