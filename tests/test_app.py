import os

from app import create_app


def test_health_returns_ok(tmp_path):
    client = create_app(data_dir=str(tmp_path)).test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_app_creates_database_file(tmp_path):
    data_dir = tmp_path / "data"

    create_app(data_dir=str(data_dir))

    assert os.path.exists(data_dir / "padel.db")
