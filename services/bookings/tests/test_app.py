import os

import pytest

from app import create_app
from tests.conftest import TEST_SECRET


def test_health_returns_ok(tmp_path):
    client = create_app(data_dir=str(tmp_path), token_secret=TEST_SECRET).test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_app_creates_database_file(tmp_path):
    data_dir = tmp_path / "data"

    create_app(data_dir=str(data_dir), token_secret=TEST_SECRET)

    assert os.path.exists(data_dir / "bookings.db")


def test_create_app_refuses_to_start_without_token_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("TOKEN_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="TOKEN_SECRET"):
        create_app(data_dir=str(tmp_path))


def test_create_app_reads_token_secret_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKEN_SECRET", "from-env")

    app = create_app(data_dir=str(tmp_path))

    assert app.config["TOKEN_SECRET"] == "from-env"
