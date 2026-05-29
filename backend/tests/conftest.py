"""Pytest fixtures. The TestClient context manager runs the app lifespan, which
warms the read-cache from Postgres — so integration tests see real loaded data.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
