from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("POWERTRACE_DATABASE_URL",
                      f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("POWERTRACE_ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("POWERTRACE_ADMIN_PASSWORD", "testpassword")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.protocols.simulator import SimulatorAdapter  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def token(client) -> str:
    response = client.post("/api/auth/token",
                           json={"email": "admin@test.local", "password": "testpassword"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth(token) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def demo_project(client, auth) -> dict:
    response = client.post("/api/demo/seed?reset=true", headers=auth)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clear_sim_faults():
    yield
    for state in SimulatorAdapter.all_states().values():
        state.fault_mode = "NONE"
