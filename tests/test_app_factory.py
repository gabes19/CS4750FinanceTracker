from app import create_app


def test_create_app_uses_testing_config():
    app = create_app({"TESTING": True})
    assert app.config["TESTING"] is True
