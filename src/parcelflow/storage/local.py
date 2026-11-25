"""Local filesystem implementation of :class:`StorageBackend`.

Blobs are stored as files under a root directory, with the blob "key" mapped
directly to a relative path. This mirrors how object stores present a flat
key space that *looks* like folders (``raw/date=2024-01-01/chennai.csv``).
"""

from __future__ import annotations

from pathlib import Path

from .base import StorageBackend


class LocalFileStorage(StorageBackend):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def write_bytes(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        # ``prefix`` may point at a directory or be a partial path; search the
        # whole root and filter by the prefix string for consistent behaviour.
        keys = []
        for p in self.root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.root).as_posix()
                if rel.startswith(prefix):
                    keys.append(rel)
        return sorted(keys)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()
