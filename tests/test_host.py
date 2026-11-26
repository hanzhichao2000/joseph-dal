from __future__ import annotations

from pathlib import Path

import pytest

from joseph_dal import LiveTransportRefused, admit, discover_providers, locate
from joseph_api import RevisionFile, RevisionRecord


def test_discovery_via_entry_points(fake_entry_points, fake_provider):
    fake_entry_points({"fake": fake_provider})
    assert discover_providers() == {"fake": fake_provider}


def test_strict_local_refuses_live_transport(fake_provider):
    fake_provider.transports = ("live", "file")
    with pytest.raises(LiveTransportRefused) as exc:
        admit(fake_provider, "strict_local")
    assert exc.value.provider_id == "fake"
    admit(fake_provider, "live")


def test_strict_local_admits_file_only(fake_provider):
    admit(fake_provider, "strict_local")


def test_locate_uses_first_listed_file():
    files = (RevisionFile(path="a/part-0.parquet", digest="0" * 64, size=1),)
    rec = RevisionRecord(
        capability_id="c",
        schema_version="1",
        source="s",
        revision_id="r",
        content_digest=RevisionRecord.compute_content_digest("c", "1", "s", files),
        files=files,
    )
    assert locate(rec, Path("/root")) == Path("/root/a/part-0.parquet")
