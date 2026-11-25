"""Central configuration for ParcelFlow.

All runtime configuration is read from environment variables (optionally loaded
from a local ``.env`` file). This keeps secrets out of the code and lets the
exact same code run locally (SQLite + local filesystem) or in a
production-like stack (PostgreSQL + Azure Blob / Azurite) just by changing
environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file if one exists. Real environment variables
# always win over .env values, which is what you want in CI / containers.
load_dotenv()

# Project root = two levels up from this file (src/parcelflow/config.py -> root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_str: str) -> str:
    """Make a possibly-relative path absolute, anchored at the project root."""
    p = Path(path_str)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of configuration for one process."""

    database_url: str
    storage_backend: str
    local_storage_root: str
    azure_connection_string: str
    azure_raw_container: str
    n_hubs: int
    volume_scale: float


def get_settings() -> Settings:
    """Build a Settings object from the current environment.

    Defaults are chosen so the project runs with zero setup: SQLite database in
    ./data and a local-filesystem blob store. No external services required.
    """
    database_url = os.getenv("DATABASE_URL", "sqlite:///data/parcelflow.db")

    # For SQLite, resolve the relative file path so the DB lands in the project
    # regardless of the current working directory.
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        rel = database_url.replace("sqlite:///", "", 1)
        database_url = "sqlite:///" + _resolve(rel)

    return Settings(
        database_url=database_url,
        storage_backend=os.getenv("STORAGE_BACKEND", "local").lower(),
        local_storage_root=_resolve(os.getenv("LOCAL_STORAGE_ROOT", "data/blob")),
        azure_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""),
        azure_raw_container=os.getenv("AZURE_RAW_CONTAINER", "raw"),
        n_hubs=int(os.getenv("PARCELFLOW_N_HUBS", "15")),
        # Downscales stored parcel counts so a full 2-year dataset fits a
        # laptop/CI while preserving the *shape* (seasonality, trends). The
        # hub base volumes read like real FedEx-scale numbers; this is the
        # single knob that scales them for local storage.
        volume_scale=float(os.getenv("VOLUME_SCALE", "0.02")),
    )
