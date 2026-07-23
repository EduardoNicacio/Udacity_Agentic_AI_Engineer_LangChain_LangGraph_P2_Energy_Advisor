import os
import pytest
from datetime import datetime
from unittest.mock import patch


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    monkeypatch.setenv("VOCAREUM_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")


@pytest.fixture
def sample_timestamp():
    return datetime(2026, 7, 1, 14, 30, 0)


@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_energy.db")
