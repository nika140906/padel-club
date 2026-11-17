import pytest

from app import create_app
from tests.conftest import TEST_SECRET


def test_starting_the_app_again_applies_no_migrations(clean_database, caplog):
    caplog.set_level("INFO")

    create_app(database_url=clean_database, token_secret=TEST_SECRET)

    assert "no migrations to apply" in caplog.text


def test_create_app_refuses_to_start_without_token_secret(clean_database, monkeypatch):
    monkeypatch.delenv("TOKEN_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="TOKEN_SECRET"):
        create_app(database_url=clean_database)


def test_create_app_refuses_to_start_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app(token_secret=TEST_SECRET)


def test_create_app_reads_settings_from_environment(clean_database, monkeypatch):
    monkeypatch.setenv("TOKEN_SECRET", "from-env")
    monkeypatch.setenv("DATABASE_URL", clean_database)

    app = create_app()

    assert app.config["TOKEN_SECRET"] == "from-env"
    assert app.config["DATABASE_URL"] == clean_database
