"""Shared pytest fixtures.

Every test runs against a throwaway SQLite database and a local blob store in a
temporary directory, so tests are fully isolated and need no external services.
"""

from __future__ import annotations

import pytest

from parcelflow.config import Settings
from parcelflow.db.engine import get_engine
from parcelflow.db.schema import create_all
from parcelflow.storage.local import LocalFileStorage


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_backend="local",
        local_storage_root=str(tmp_path / "blob"),
        azure_connection_string="",
        azure_raw_container="raw",
        n_hubs=15,
        volume_scale=0.01,  # tiny dataset keeps tests fast
    )


@pytest.fixture
def engine(settings):
    eng = get_engine(settings.database_url)
    create_all(eng)
    return eng


@pytest.fixture
def storage(settings):
    return LocalFileStorage(settings.local_storage_root)
