import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fixture_path():
    def _path(name: str) -> str:
        return os.path.join(FIXTURES_DIR, name)

    return _path
