"""Publish complete user exports atomically, never replace an existing original."""
import os
from pathlib import Path
import tempfile


def publish_new(path: Path, content: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic no-clobber publication on the same filesystem, including NTFS.
        # If hard links are unsupported, fail safely rather than fall back to overwrite.
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
