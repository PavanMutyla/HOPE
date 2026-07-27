"""Content-addressed blob store for episodic media (images, audio, ...).

Bytes are stored once per unique sha256 hash under
`<media_dir>/<hash[:2]>/<hash>` — identical content written twice is a no-op
on the second write, so the same image referenced across many episodes costs
storage once. There is no file extension: the hash is the sole identity, and
`mime` is tracked separately (see episodic.py's `media` table) rather than
folded into the filename — that keeps a single piece of content from forking
into two paths just because a caller declared a different mime the second
time it was seen.
"""

import hashlib
from pathlib import Path

from memory.episodic_memory.schema import MediaRef


def path_for_hash(media_dir: Path, hash_: str) -> Path:
    return Path(media_dir) / hash_[:2] / hash_


def store_bytes(data: bytes, mime: str, media_dir: Path) -> MediaRef:
    """Write `data` under its content hash if not already present. Idempotent."""
    hash_ = hashlib.sha256(data).hexdigest()
    path = path_for_hash(media_dir, hash_)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return MediaRef(hash=hash_, path=str(path), mime=mime, size=len(data))
