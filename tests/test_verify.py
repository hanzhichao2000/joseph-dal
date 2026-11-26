from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from joseph_api import RevisionFile, RevisionRecord
from joseph_dal import RevisionVerificationError, verify_revision


def _build(root: Path) -> RevisionRecord:
    (root / "part-0.parquet").write_bytes(b"hello")
    (root / "sub").mkdir()
    (root / "sub" / "part-1.parquet").write_bytes(b"world!")
    files = (
        RevisionFile(
            path="part-0.parquet", digest=__import__("hashlib").sha256(b"hello").hexdigest(), size=5
        ),
        RevisionFile(
            path="sub/part-1.parquet",
            digest=__import__("hashlib").sha256(b"world!").hexdigest(),
            size=6,
        ),
    )
    return RevisionRecord(
        capability_id="option_bars",
        schema_version="1",
        source="cnequity@0.25.0",
        revision_id="r",
        content_digest=RevisionRecord.compute_content_digest(
            "option_bars", "1", "cnequity@0.25.0", files
        ),
        files=files,
    )


def test_verify_passes_and_relocates(tmp_path: Path):
    root = tmp_path / "rev"
    root.mkdir()
    rec = _build(root)
    verify_revision(root, rec)
    moved = tmp_path / "moved"
    shutil.move(str(root), str(moved))
    verify_revision(moved, rec)


def test_missing_file_fails_by_name(tmp_path: Path):
    root = tmp_path / "rev"
    root.mkdir()
    rec = _build(root)
    (root / "sub" / "part-1.parquet").unlink()
    with pytest.raises(RevisionVerificationError) as exc:
        verify_revision(root, rec)
    assert exc.value.missing == "sub/part-1.parquet"


def test_tampered_file_fails(tmp_path: Path):
    root = tmp_path / "rev"
    root.mkdir()
    rec = _build(root)
    (root / "part-0.parquet").write_bytes(b"HELLO")
    with pytest.raises(RevisionVerificationError):
        verify_revision(root, rec)
