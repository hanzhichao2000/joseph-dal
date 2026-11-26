"""Whole-revision verification: every listed file exists, has the recorded size and digest; a
missing file fails by name and nothing is read partially."""

from __future__ import annotations

import hashlib
from pathlib import Path

from joseph_api import RevisionRecord

from joseph_dal.exceptions import RevisionVerificationError


def _digest(path: Path) -> str:
    """hashlib.file_digest: C-implemented, constant memory, no Python chunk loop (3.11+)."""
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def verify_revision(root: Path, record: RevisionRecord) -> None:
    for entry in record.files:
        path = root / entry.path
        if not path.is_file():
            raise RevisionVerificationError(
                f"revision {record.revision_id!r}: missing file {entry.path!r}", missing=entry.path
            )
    for entry in record.files:
        path = root / entry.path
        size = path.stat().st_size
        if size != entry.size:
            raise RevisionVerificationError(
                f"revision {record.revision_id!r}: {entry.path!r} size {size} != {entry.size}"
            )
        digest = _digest(path)
        if digest != entry.digest:
            raise RevisionVerificationError(
                f"revision {record.revision_id!r}: {entry.path!r} digest mismatch"
            )
    expected = RevisionRecord.compute_content_digest(
        record.capability_id, record.schema_version, record.source, record.files
    )
    if expected != record.content_digest:
        raise RevisionVerificationError(f"revision {record.revision_id!r}: content digest mismatch")
