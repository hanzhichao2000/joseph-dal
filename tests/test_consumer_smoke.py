from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fake_cne import default_lake
from joseph_api import RevisionFile, RevisionRecord, RevisionWindow

from joseph_dal import LiveTransportRefused, admit, discover_providers, verify_revision


def test_discovered_option_declarations(cne, monkeypatch):
    executable = Path(cne(default_lake()))
    monkeypatch.setenv("PATH", str(executable.parent))
    provider = discover_providers()["cnequity"]
    declarations = {item.capability_id: item for item in provider.capabilities}
    for name, mode, start, derived in (
        ("option_contracts", "snapshot_only", None, None),
        ("option_bars", "by_date", date(2023, 11, 1), None),
        ("option_greeks", "by_date", date(2023, 11, 1), ("option_bars", "option_contracts")),
    ):
        item = declarations[name]
        assert (item.history_mode, item.coverage_start, item.derived_from, item.window_limits) == (
            mode,
            start,
            derived,
            None,
        )
    with pytest.raises(LiveTransportRefused):
        admit(provider, "strict_local")


def test_recorded_receipt_reads_only_parquet_without_provider(monkeypatch, tmp_path):
    root = Path(__file__).parent / "fixtures" / "option-revision"
    record = RevisionRecord.from_json((root / "option_bars.revision.json").read_text())

    def refuse_construction(*args, **kwargs):
        pytest.fail("provider constructed during receipt read")

    monkeypatch.setattr("joseph_dal_cnequity.CnequityProvider.__init__", refuse_construction)
    monkeypatch.setattr(
        "joseph_dal.host.discover_providers", lambda: pytest.fail("provider loaded")
    )
    verify_revision(root, record)
    tables = [
        pq.read_table(root / item.path) for item in record.files if item.path.endswith(".parquet")
    ]
    assert len(tables) == 1
    assert tables[0].column("symbol").to_pylist() == ["X"]
    assert any(item.path.endswith(".coverage.json") for item in record.files)

    second_root = tmp_path / "second"
    second_root.mkdir()
    parquet = second_root / "part.parquet"
    pq.write_table(pa.table({"symbol": ["Y"], "trade_date": [date(2024, 1, 2)]}), parquet)
    files = (
        RevisionFile(
            path=parquet.name,
            digest=sha256(parquet.read_bytes()).hexdigest(),
            size=parquet.stat().st_size,
        ),
    )
    second = RevisionRecord(
        capability_id=record.capability_id,
        schema_version=record.schema_version,
        source=record.source,
        revision_id=record.revision_id,
        window=RevisionWindow(start=date(2024, 1, 2), end=date(2024, 1, 2)),
        files=files,
        content_digest=RevisionRecord.compute_content_digest(
            record.capability_id, record.schema_version, record.source, files
        ),
    )
    (second_root / "option_bars.revision.json").write_text(second.to_json())
    second = RevisionRecord.from_json((second_root / "option_bars.revision.json").read_text())
    assert (
        record.revision_id
        == second.revision_id
        == "option_bars@lake:dd97f8582206451f831c53f4cc6afce2"
    )
    assert record.window != second.window and record.content_digest != second.content_digest
    verify_revision(second_root, second)
    assert pq.read_table(second_root / second.files[0].path).column("symbol").to_pylist() == ["Y"]
