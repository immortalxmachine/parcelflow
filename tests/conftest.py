"""Shared pytest fixtures.

Every test runs against a throwaway SQLite database and a local blob store in a
temporary directory, so tests are fully isolated and need no external services.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parcelflow.config import Settings
from parcelflow.db.engine import get_engine
from parcelflow.db.schema import create_all
from parcelflow.storage.local import LocalFileStorage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OLIST_DIR = PROJECT_ROOT / "data" / "raw" / "olist"
OLIST_ORDERS = OLIST_DIR / "olist_orders_dataset.csv"


@pytest.fixture
def settings(tmp_path) -> Settings:
    # The source-backed tests need the real Olist CSVs. If they are not present
    # (e.g. CI without the Kaggle download), skip rather than fail. Quality and
    # storage tests build their own data and do not use this fixture.
    if not OLIST_ORDERS.exists():
        pytest.skip(
            "Olist dataset not found under data/raw/olist "
            "(download with: kaggle datasets download -d "
            "olistbr/brazilian-ecommerce -p data/raw/olist --unzip)"
        )
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_backend="local",
        local_storage_root=str(tmp_path / "blob"),
        azure_connection_string="",
        azure_raw_container="raw",
        # Point at the real Olist CSVs committed/downloaded under data/raw.
        olist_dir=str(PROJECT_ROOT / "data" / "raw" / "olist"),
    )


@pytest.fixture
def engine(settings):
    eng = get_engine(settings.database_url)
    create_all(eng)
    return eng


@pytest.fixture
def storage(settings):
    return LocalFileStorage(settings.local_storage_root)
