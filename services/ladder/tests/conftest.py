import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pymssql
import pytest

from app import create_app
from padel.auth.tokens import make_token, read_token
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


class BookingsStub:
    """A stand-in for the bookings service: a real HTTP server on a free local port.

    It answers GET /auth/me the way the real bookings service does, reading
    the user id from the token. mode decides how it behaves:
    "ok" (200), "missing" (404), "broken" (500), "slow" (answers after 1 s)
    or "not_json". received_auth records the Authorization headers it got.
    """

    def __init__(self):
        self.mode = "ok"
        self.received_auth = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                stub.received_auth.append(self.headers.get("Authorization"))
                if stub.mode == "slow":
                    time.sleep(1)
                if self.path != "/auth/me" or stub.mode == "missing":
                    return self.reply(404, {"error": "account not found"})
                if stub.mode == "broken":
                    return self.reply(500, {"error": "internal server error"})
                if stub.mode == "not_json":
                    return self.reply(200, "hello")
                user_id = read_token(TEST_SECRET, self.headers["Authorization"].split(" ", 1)[1])
                self.reply(200, {"id": user_id, "username": f"member{user_id}"})

            def reply(self, status, body):
                data = (json.dumps(body) if isinstance(body, dict) else body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # keep the test output quiet
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, args=(0.05,), daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def bookings_stub():
    stub = BookingsStub()
    yield stub
    stub.stop()


@pytest.fixture
def client(clean_database, bookings_stub):
    """A test client for an app that uses the empty test database and the bookings stub."""
    app = create_app(
        database_url=clean_database, token_secret=TEST_SECRET, bookings_url=bookings_stub.url
    )
    return app.test_client()


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
