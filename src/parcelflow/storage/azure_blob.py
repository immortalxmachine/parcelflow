"""Azure Blob Storage implementation of :class:`StorageBackend`.

Works unchanged against a real Azure Storage account or the Azurite emulator
(the Docker Compose stack runs Azurite), because both speak the same API and
are selected purely through the connection string.

The ``azure-storage-blob`` import is done lazily inside ``__init__`` so that the
rest of the project (and the test suite) can run without the Azure SDK
installed when the local backend is used.
"""

from __future__ import annotations

from .base import StorageBackend


class AzureBlobStorage(StorageBackend):
    def __init__(self, connection_string: str, container: str) -> None:
        from azure.storage.blob import BlobServiceClient  # lazy import

        if not connection_string:
            raise ValueError(
                "AZURE_STORAGE_CONNECTION_STRING is required for the azure "
                "storage backend."
            )
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self.container = container
        self._ensure_container()

    def _ensure_container(self) -> None:
        client = self._service.get_container_client(self.container)
        if not client.exists():
            client.create_container()

    def write_bytes(self, key: str, data: bytes) -> str:
        blob = self._service.get_blob_client(self.container, key)
        blob.upload_blob(data, overwrite=True)  # overwrite => idempotent re-runs
        return f"azure://{self.container}/{key}"

    def read_bytes(self, key: str) -> bytes:
        blob = self._service.get_blob_client(self.container, key)
        return blob.download_blob().readall()

    def list_keys(self, prefix: str) -> list[str]:
        client = self._service.get_container_client(self.container)
        return sorted(b.name for b in client.list_blobs(name_starts_with=prefix))

    def exists(self, key: str) -> bool:
        return self._service.get_blob_client(self.container, key).exists()
