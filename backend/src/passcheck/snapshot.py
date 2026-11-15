"""Last-good upstream responses on disk, so a restart serves data immediately.

One file per source holds the latest raw response and when we fetched it, overwritten on
every successful fetch (no history). On startup each snapshot is re-parsed by its source and
restored with its *original* fetch time, so the normal staleness rules still apply:

- live road data older than the live window no longer escalates anything, and a configured
  live source that is stale floors near-term verdicts at CAUTION;
- a forecast older than the forecast window floors every verdict at CAUTION.

A restart therefore can never present old data as current. Snapshots older than
``MAX_RESTORE_AGE`` are ignored entirely. Raw upstream responses never contain our API keys
(keys only travel in request URLs, which are not stored).
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("passcheck.snapshot")

SCHEMA = 1
MAX_RESTORE_AGE = timedelta(hours=24)
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
_NAME = re.compile(r"^[a-z0-9_]{1,32}$")


@dataclass(frozen=True, slots=True)
class Snapshot:
    raw: bytes
    fetched_at: datetime


class SnapshotDir:
    """Atomic per-source snapshot files under ``root``. Disabled (no-op) when unwritable."""

    def __init__(self, root: Path | None) -> None:
        self.root = root if root is not None and self._writable(root) else None

    @property
    def enabled(self) -> bool:
        return self.root is not None

    @staticmethod
    def _writable(root: Path) -> bool:
        try:
            root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=root, prefix=".probe-"):
                pass
            return True
        except OSError as exc:
            log.warning("snapshots disabled: %s is not writable (%s)", root, type(exc).__name__)
            return False

    def _paths(self, name: str) -> tuple[Path, Path]:
        if self.root is None or not _NAME.match(name):
            raise ValueError("invalid snapshot name")
        return self.root / f"{name}.bin", self.root / f"{name}.json"

    def save(self, name: str, raw: bytes, fetched_at: datetime) -> None:
        """Write raw + metadata atomically (temp file + rename). Never raises."""
        if self.root is None or not raw or len(raw) > MAX_SNAPSHOT_BYTES:
            return
        try:
            data_path, meta_path = self._paths(name)
            meta = {"schema": SCHEMA, "fetched_at": fetched_at.isoformat(), "size": len(raw)}
            # Data first, then metadata: a crash between the two leaves the old metadata,
            # whose size check then rejects the mismatched data file on load.
            self._atomic_write(data_path, raw)
            self._atomic_write(meta_path, json.dumps(meta).encode())
        except (OSError, ValueError) as exc:
            log.warning("snapshot save failed source=%s error=%s", name, type(exc).__name__)

    def _atomic_write(self, path: Path, data: bytes) -> None:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def load(self, name: str, now: datetime) -> Snapshot | None:
        """The stored snapshot, or None if missing, unreadable, too old or from the future."""
        if self.root is None:
            return None
        try:
            data_path, meta_path = self._paths(name)
            if not meta_path.is_file() or not data_path.is_file():
                return None
            meta = json.loads(meta_path.read_bytes())
            if meta.get("schema") != SCHEMA:
                return None
            fetched_at = datetime.fromisoformat(meta["fetched_at"])
            if fetched_at.tzinfo is None or fetched_at > now or now - fetched_at > MAX_RESTORE_AGE:
                return None
            size = int(meta["size"])
            if size <= 0 or size > MAX_SNAPSHOT_BYTES or data_path.stat().st_size != size:
                return None
            return Snapshot(data_path.read_bytes(), fetched_at)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("snapshot unreadable source=%s error=%s", name, type(exc).__name__)
            return None
