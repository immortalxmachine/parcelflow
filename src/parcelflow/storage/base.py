"""Storage abstraction (Strategy pattern).

The pipeline treats blob storage as an interface with two operations: write a
blob and read it back. Two concrete strategies implement it:

* ``LocalFileStorage``  - plain filesystem, zero dependencies, used in dev/CI.
* ``AzureBlobStorage``  - Azure Blob Storage, also works against the Azurite
                          emulator for a fully-local "cloud" experience.

Because the pipeline depends only on this interface, swapping storage backends
is a one-line config change and never touches pipeline logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Minimal blob-storage interface used by the extract step."""

    @abstractmethod
    def write_bytes(self, key: str, data: bytes) -> str:
        """Store ``data`` under ``key`` (e.g. ``raw/date=2024-01-01/hub.csv``).

        Returns a URI/path identifying the stored blob.
        """

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        """Return the bytes previously stored under ``key``."""

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]:
        """Return all keys that start with ``prefix``, sorted."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if a blob exists under ``key``."""
