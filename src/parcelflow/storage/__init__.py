"""Storage backends and a factory that selects one from configuration."""

from __future__ import annotations

from ..config import Settings, get_settings
from .base import StorageBackend
from .local import LocalFileStorage


def get_storage(settings: Settings | None = None) -> StorageBackend:
    """Return the storage backend selected by configuration.

    This is the single place that knows about concrete backends; the rest of
    the pipeline depends only on the :class:`StorageBackend` interface.
    """
    settings = settings or get_settings()
    backend = settings.storage_backend

    if backend == "local":
        return LocalFileStorage(settings.local_storage_root)
    if backend == "azure":
        # Imported lazily so the Azure SDK is only needed when actually used.
        from .azure_blob import AzureBlobStorage

        return AzureBlobStorage(
            settings.azure_connection_string, settings.azure_raw_container
        )
    raise ValueError(f"Unknown STORAGE_BACKEND: {backend!r} (use 'local' or 'azure')")


__all__ = ["StorageBackend", "LocalFileStorage", "get_storage"]
