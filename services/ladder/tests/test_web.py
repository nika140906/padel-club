"""Health check, CORS and request logs. This file is the same in both services."""
from padel.db import connect

UI_ORIGIN = "http://localhost:8080"  # the default CORS_ORIGIN


def test_health_returns_ok_when_the_database_works(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "dev"}


def test_health_shows_the_git_sha_it_was_built_from(clean_database, monkeypatch):
    from app import create_app
    from tests.conftest import TEST_SECRET

    monkeypatch.setenv("GIT_SHA", "abc1234")
    client = create_app(database_url=clean_database, token_secret=TEST_SECRET).test_client()

    assert client.get("/health").get_json()["version"] == "abc1234"


def test_health_returns_503_when_the_database_cannot_be_reached(client):
    # Same server, but a database that does not exist, so the login fails.
    url = client.application.config["DATABASE_URL"]
    client.application.config["DATABASE_URL"] = url.rsplit("/", 1)[0] + "/no_such_database"

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json()["status"] == "error"
    assert response.get_json()["db"] == "error"


def test_health_check_leaves_nothing_behind(client, clean_database):
    client.get("/health")

    conn = connect(clean_database)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM schema_migrations WHERE version = 'health-check'"
        ).fetchone()
    finally:
        conn.close()
    assert row["n"] == 0


def test_cors_allows_the_ui_origin(client):
    response = client.get("/health", headers={"Origin": UI_ORIGIN})

    assert response.headers["Access-Control-Allow-Origin"] == UI_ORIGIN


def test_cors_ignores_other_origins(client):
    response = client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_preflight_allows_the_token_header_without_login(client):
    # The browser asks first, without a token, before sending a POST with one.
    response = client.options("/health", headers={
        "Origin": UI_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type",
    })

    assert response.status_code == 200
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    assert "POST" in response.headers["Access-Control-Allow-Methods"]


def test_cors_origin_comes_from_the_environment(clean_database, monkeypatch):
    from app import create_app
    from tests.conftest import TEST_SECRET

    monkeypatch.setenv("CORS_ORIGIN", "https://padel-ui.example.net")
    client = create_app(database_url=clean_database, token_secret=TEST_SECRET).test_client()

    response = client.get("/health", headers={"Origin": "https://padel-ui.example.net"})
    assert response.headers["Access-Control-Allow-Origin"] == "https://padel-ui.example.net"
    response = client.get("/health", headers={"Origin": UI_ORIGIN})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_every_request_is_logged_with_method_path_status_and_duration(client, caplog):
    caplog.set_level("INFO", logger="padel.requests")

    client.get("/no-such-page")

    assert len(caplog.records) == 1
    assert caplog.records[0].getMessage().startswith("GET /no-such-page 404 ")
    assert caplog.records[0].getMessage().endswith("ms")
