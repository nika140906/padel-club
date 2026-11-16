import os

import pymssql
import pytest

from app import create_app
from padel.auth.tokens import make_token
from padel.db import connect, parse_database_url
from padel.migrate import migrate

TEST_SECRET = "test-secret"


def get_test_database_url():
    """Where the tests may create and wipe their own database.

    Example: mssql://sa:<password>@localhost:1433/ladder_test
    The database named at the end is dropped and created again on every run,
    so never point this at a database with real data.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set; see the README section on running tests")
    return url


def recreate_database(url):
    """Drop the database named in the URL (if it exists) and create it empty."""
    settings = parse_database_url(url)
    name = settings.pop("database")
    # CREATE/DROP DATABASE cannot run inside a transaction, hence autocommit.
    server = pymssql.connect(**settings, database="master", autocommit=True)
    try:
        cursor = server.cursor()
        cursor.execute(
            f"IF DB_ID(N'{name}') IS NOT NULL BEGIN "
            f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE [{name}]; END"
        )
        cursor.execute(f"CREATE DATABASE [{name}]")
    finally:
        server.close()


@pytest.fixture(scope="session")
def database_url():
    """A fresh test database with all migrations applied, made once per test run."""
    url = get_test_database_url()
    recreate_database(url)
    conn = connect(url)
    try:
        migrate(conn)
    finally:
        conn.close()
    return url


@pytest.fixture
def clean_database(database_url):
    """Remove the rows earlier tests left behind."""
    conn = connect(database_url)
    try:
        conn.execute("DELETE FROM matches; DELETE FROM players;")
        conn.commit()
    finally:
        conn.close()
    return database_url


@pytest.fixture
def conn(clean_database):
    """A connection to the empty test database."""
    connection = connect(clean_database)
    yield connection
    connection.close()


@pytest.fixture
def client(clean_database):
    """A test client for an app that uses the empty test database."""
    return create_app(database_url=clean_database, token_secret=TEST_SECRET).test_client()


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
