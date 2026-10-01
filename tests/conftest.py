import pytest

from app import create_app
from padel.db import connect, get_db_path, init_db


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
    return create_app(data_dir=str(tmp_path)).test_client()


def log_in_as(client, username, password="secret123"):
    """Register a user and log them in on this client."""
    client.post("/auth/register", json={"username": username, "password": password})
    client.post("/auth/login", json={"username": username, "password": password})


@pytest.fixture
def logged_in_client(client):
    """A test client where the user "nika" is logged in."""
    log_in_as(client, "nika")
    return client
