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


def test_login_then_me_returns_current_user(client):
    register(client)
    login(client)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.get_json()["username"] == "nika"


def test_login_with_wrong_password_returns_401(client):
    register(client)

    response = login(client, password="wrong-password")

    assert response.status_code == 401


def test_logout_ends_the_session(client):
    register(client)
    login(client)

    client.post("/auth/logout")

    assert client.get("/auth/me").status_code == 401
