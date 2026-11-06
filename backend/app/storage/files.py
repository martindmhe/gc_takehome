# local file storage interface, swapped for s3 in production

import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import get_settings

CHUNK_SIZE = 64 * 1024
_KEY_PATTERN = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{32}\.pdf$")


def new_key() -> str:
    """A random storage key like `3f/3f2a...c1.pdf`. The prefix keeps directories small."""
    name = uuid.uuid4().hex
    return f"{name[:2]}/{name}.pdf"


class FileStorage(Protocol):
    def save(self, key: str, chunks: Iterator[bytes]) -> None:
        """Store the bytes under a new key. Fails if the key already exists."""
        ...

    def open(self, key: str) -> Iterator[bytes]:
        """Stream a stored file's bytes in chunks."""
        ...

    def delete(self, key: str) -> None:
        """Remove a stored file. Missing files are ignored."""
        ...


class LocalFileStorage:
    """Stores files under a root directory that is never served statically."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        # Keys are server-generated, but check anyway so a bad key can never
        # point outside the root (e.g. `../../etc/passwd`).
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid storage key: {key!r}")
        return self.root / key

    def save(self, key: str, chunks: Iterator[bytes]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as f:  # "x": never overwrite an existing file
                for chunk in chunks:
                    f.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)  # don't leave a partial file behind
            raise

    def open(self, key: str) -> Iterator[bytes]:
        # Open now, so a missing file fails before a response starts streaming.
        f = self._path(key).open("rb")

        def chunks() -> Iterator[bytes]:
            with f:
                yield from read_chunks(f)

        return chunks()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def get_storage() -> FileStorage:
    """FastAPI dependency; tests override it with a temporary directory."""
    return LocalFileStorage(get_settings().storage_dir)


def read_chunks(file: BinaryIO) -> Iterator[bytes]:
    while chunk := file.read(CHUNK_SIZE):
        yield chunk
