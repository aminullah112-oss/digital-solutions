"""Backend tests. They use a fake Kite client, so no real credentials or
network are needed.  Run from backend/:   pytest
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kiteconnect import exceptions as kite_exc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402

SECRET_TOKEN = "super-secret-access-token-123"
API_SECRET = "my-api-secret-xyz"

PROFILE = {
    "user_id": "AB1234",
    "user_name": "Test User",
    "email": "private@example.com",
    "products": ["CNC", "MIS", "NRML"],
    "exchanges": ["NSE", "BSE", "NFO"],
}


class FakeKite:
    valid_tokens = {SECRET_TOKEN}
    invalidated = []

    def __init__(self, api_key, timeout=None):
        self.api_key = api_key
        self.token = None

    def generate_session(self, request_token, api_secret):
        if request_token != "good-request-token" or api_secret != API_SECRET:
            raise kite_exc.TokenException("Token is invalid or has expired.")
        return {"access_token": SECRET_TOKEN, "user_id": "AB1234", "user_name": "Test User"}

    def set_access_token(self, token):
        self.token = token

    def profile(self):
        if self.token not in self.valid_tokens:
            raise kite_exc.TokenException("Incorrect `api_key` or `access_token`.")
        return PROFILE

    def invalidate_access_token(self, token):
        FakeKite.invalidated.append(token)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    session_file = tmp_path / "session.json"
    monkeypatch.setenv("KITE_SESSION_FILE", str(session_file))
    monkeypatch.setattr(main, "KiteConnect", FakeKite)
    FakeKite.valid_tokens = {SECRET_TOKEN}
    FakeKite.invalidated = []
    return session_file


def login(client, **overrides):
    body = {"api_key": "key123", "api_secret": API_SECRET, "request_token": "good-request-token"}
    body.update(overrides)
    return client.post("/api/auth/login", json=body)


def test_login_success_never_returns_token_or_secret(isolated):
    client = TestClient(main.app)
    res = login(client)
    assert res.status_code == 200
    assert res.json() == {"logged_in": True, "user_id": "AB1234", "user_name": "Test User"}
    assert SECRET_TOKEN not in res.text
    assert API_SECRET not in res.text
    assert SECRET_TOKEN not in str(res.headers)


def test_login_saves_token_but_not_api_secret(isolated):
    login(TestClient(main.app))
    saved = json.loads(isolated.read_text())
    assert saved["access_token"] == SECRET_TOKEN
    assert saved["api_key"] == "key123"
    assert API_SECRET not in isolated.read_text()


def test_login_trims_whitespace(isolated):
    res = login(
        TestClient(main.app),
        api_key="  key123 ",
        api_secret=f" {API_SECRET}\n",
        request_token=" good-request-token ",
    )
    assert res.status_code == 200


def test_bad_request_token_is_400_and_saves_nothing(isolated):
    res = login(TestClient(main.app), request_token="bad")
    assert res.status_code == 400
    assert "Kite rejected the login" in res.json()["detail"]
    assert not isolated.exists()


def test_wrong_secret_does_not_echo_it(isolated):
    res = login(TestClient(main.app), api_secret="wrong-secret-value")
    assert res.status_code == 400
    assert "wrong-secret-value" not in res.text


def test_empty_fields_rejected(isolated):
    res = login(TestClient(main.app), request_token="   ")
    assert res.status_code == 422


def test_session_survives_backend_restart(isolated):
    login(TestClient(main.app))
    # A brand-new client/app instance stands in for `uvicorn --reload`.
    # Nothing is kept in memory, only the file.
    fresh = TestClient(main.app)
    status = fresh.get("/api/auth/status").json()
    assert status == {"logged_in": True, "user_id": "AB1234", "user_name": "Test User"}


def test_status_logged_out_when_no_file(isolated):
    assert TestClient(main.app).get("/api/auth/status").json() == {"logged_in": False}


def test_expired_token_is_cleared(isolated):
    client = TestClient(main.app)
    login(client)
    FakeKite.valid_tokens = set()  # Kite now rejects it (e.g. next morning)
    status = client.get("/api/auth/status").json()
    assert status == {"logged_in": False, "reason": "expired"}
    assert not isolated.exists()


def test_profile_returns_only_dashboard_fields(isolated):
    client = TestClient(main.app)
    login(client)
    res = client.get("/api/profile")
    assert res.status_code == 200
    assert res.json() == {
        "user_name": "Test User",
        "user_id": "AB1234",
        "products": ["CNC", "MIS", "NRML"],
        "exchanges": ["NSE", "BSE", "NFO"],
    }
    assert "private@example.com" not in res.text
    assert SECRET_TOKEN not in res.text


def test_profile_401_when_not_logged_in(isolated):
    assert TestClient(main.app).get("/api/profile").status_code == 401


def test_profile_401_when_token_expired(isolated):
    client = TestClient(main.app)
    login(client)
    FakeKite.valid_tokens = set()
    assert client.get("/api/profile").status_code == 401


def test_logout_clears_file_and_invalidates_token(isolated):
    client = TestClient(main.app)
    login(client)
    assert client.post("/api/auth/logout").json() == {"logged_in": False}
    assert not isolated.exists()
    assert FakeKite.invalidated == [SECRET_TOKEN]
    assert client.get("/api/profile").status_code == 401
