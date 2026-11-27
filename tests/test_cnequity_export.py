from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fake_cne import COVERAGE_START, LakeConfigurer, default_lake
from joseph_dal_cnequity import CnequityProvider, load_receipt

from joseph_dal import verify_revision
from joseph_dal.protocols import Window


def test_export_produces_verifiable_revision(cne: LakeConfigurer, tmp_path: Path) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    out = tmp_path / "out"
    rec = provider.export("option_bars", Window(start=date(2024, 1, 2), end=date(2024, 3, 29)), out)
    assert rec.source == "cnequity@0.25.0"
    assert {f.path for f in rec.files} == {
        "option_bars/year=2024/month=1/data_0.parquet",
        "option_bars/year=2024/month=2/data_0.parquet",
        "option_bars/year=2024/month=3/data_0.parquet",
    }
    assert all(not p.startswith("/") for p in (f.path for f in rec.files))
    verify_revision(out, rec)
    assert load_receipt(out / "option_bars.revision.json") == rec
    assert rec.revision_id == "option_bars@lake:dd97f8582206451f831c53f4cc6afce2"


def test_undated_dataset_exports_without_window(cne: LakeConfigurer, tmp_path: Path) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    out = tmp_path / "out2"
    rec = provider.export("option_contracts", None, out)
    assert (
        rec.window is None
        and rec.revision_id == "option_contracts@lake:dd97f8582206451f831c53f4cc6afce2"
    )
    verify_revision(out, rec)


def test_dated_dataset_requires_a_window(cne: LakeConfigurer, tmp_path: Path) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    with pytest.raises(ValueError, match="window is required"):
        provider.export("option_bars", None, tmp_path / "out3")


def test_capabilities_declare_source_and_history_mode(cne: LakeConfigurer) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    caps = {c.capability_id: c for c in provider.capabilities}
    assert caps["option_bars"].source == "cnequity@0.25.0"
    assert caps["option_bars"].history_mode == "by_date"
    assert caps["option_bars"].coverage_start == COVERAGE_START
    assert provider.replay_policy == "idempotent_refetch"
