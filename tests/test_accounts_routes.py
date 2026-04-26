from app import create_app


def _test_config() -> dict[str, object]:
    return {"TESTING": True, "SECRET_KEY": "test-secret"}


def test_accounts_index_redirects_when_unauthenticated():
    app = create_app(_test_config())
    client = app.test_client()

    response = client.get("/accounts/")

    assert response.status_code == 302
    assert "/auth/" in response.headers["Location"]


def test_accounts_api_requires_authentication():
    app = create_app(_test_config())
    client = app.test_client()

    response = client.get("/accounts/api")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Authentication required."


def test_accounts_api_returns_user_accounts(monkeypatch):
    app = create_app(_test_config())
    client = app.test_client()

    monkeypatch.setattr(
        "app.routes.accounts.list_user_accounts_with_balance",
        lambda user_id: [{"account_id": 7, "account_name": "Primary", "current_balance": 123.45}]
        if user_id == 99
        else [],
    )

    with client.session_transaction() as session:
        session["user_id"] = 99

    response = client.get("/accounts/api")

    assert response.status_code == 200
    assert response.get_json()["accounts"][0]["account_name"] == "Primary"


def test_add_funds_api_returns_updated_account(monkeypatch):
    app = create_app(_test_config())
    client = app.test_client()

    def _fake_add_funds(user_id, payload):
        assert user_id == 3
        assert payload["account_id"] == "8"
        assert payload["amount"] == "25.00"
        return {"account_id": 8, "account_name": "Cash", "current_balance": 75.0}

    monkeypatch.setattr("app.routes.accounts.add_funds_to_account", _fake_add_funds)

    with client.session_transaction() as session:
        session["user_id"] = 3

    response = client.post("/accounts/api/add-funds", json={"account_id": "8", "amount": "25.00"})

    body = response.get_json()
    assert response.status_code == 200
    assert body["message"] == "Funds added."
    assert body["account"]["current_balance"] == 75.0
