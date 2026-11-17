from padel.auth.tokens import make_token
from tests.conftest import TEST_SECRET, use_token


def register(client, username="nika", password="secret123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="nika", password="secret123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_register_returns_201(client):
    response = register(client)

    assert response.status_code == 201
    assert response.get_json()["username"] == "nika"


def test_register_with_bad_input_returns_400(client):
    response = client.post("/auth/register", json={"username": "ab"})

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_without_json_body_returns_400(client):
    response = client.post("/auth/register", data="not json")

    assert response.status_code == 400


def test_me_requires_login(client):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.get_json() == {"error": "login required"}


def test_login_returns_a_token(client):
    register(client)

    response = login(client)

    assert response.status_code == 200
    assert response.get_json()["token"]


def test_login_then_me_returns_current_user(client):
    register(client)
    use_token(client, login(client).get_json()["token"])

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.get_json()["username"] == "nika"


def test_me_for_an_account_that_no_longer_exists_returns_404(client):
    # A correctly signed token for a user id that is not in the database.
    # The ladder service relies on this 404 when a member joins.
    use_token(client, make_token(TEST_SECRET, 999))

    response = client.get("/auth/me")

    assert response.status_code == 404
    assert response.get_json() == {"error": "account not found"}


def test_login_with_wrong_password_returns_401(client):
    register(client)

    response = login(client, password="wrong-password")

    assert response.status_code == 401


def test_me_with_a_fake_token_returns_401(client):
    use_token(client, "not-a-real-token")

    assert client.get("/auth/me").status_code == 401


def test_me_with_wrong_auth_scheme_returns_401(client):
    register(client)
    token = login(client).get_json()["token"]

    response = client.get("/auth/me", headers={"Authorization": f"Basic {token}"})

    assert response.status_code == 401
