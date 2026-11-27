from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fake_cne import COVERAGE_START, LakeConfigurer, default_lake
from joseph_dal_cnequity import CnequityProvider

from joseph_dal import verify_revision
from joseph_dal.protocols import Window


def test_dataset_table_pins_modes_coverage_and_derivation(
    cne: LakeConfigurer,
) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    caps = {c.capability_id: c for c in provider.capabilities}
    assert caps["option_bars"].history_mode == "by_date"
    assert caps["option_greeks"].history_mode == "by_date"
    assert caps["index_constituents"].history_mode == "snapshot_with_backfill"
    for name in ("option_contracts", "futures_contracts", "instruments"):
        assert caps[name].history_mode == "snapshot_only", name
    assert caps["option_bars"].coverage_start == COVERAGE_START
    assert caps["option_greeks"].coverage_start == COVERAGE_START
    assert caps["index_constituents"].coverage_start is None
    assert caps["option_greeks"].derived_from == ("option_bars", "option_contracts")
    assert caps["option_bars"].derived_from is None
    assert all(c.window_limits is None for c in caps.values())


def test_window_before_coverage_start_is_refused_before_any_lake_call(
    cne: LakeConfigurer, lake_calls: list[list[str]], tmp_path: Path
) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    with pytest.raises(ValueError, match="2023-11-26"):
        provider.export(
            "option_bars", Window(start=date(2023, 11, 1), end=date(2023, 12, 29)), tmp_path
        )
    assert lake_calls == []


def test_window_from_coverage_start_is_accepted(cne: LakeConfigurer, tmp_path: Path) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    window = Window(start=COVERAGE_START, end=date(2023, 12, 29))
    record = provider.export("option_bars", window, tmp_path)
    assert record.window is not None and record.window.start == COVERAGE_START
    verify_revision(tmp_path, record)


def test_snapshot_only_refuses_a_window_before_any_lake_call(
    cne: LakeConfigurer, lake_calls: list[list[str]], tmp_path: Path
) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    with pytest.raises(ValueError, match="option_contracts"):
        provider.export(
            "option_contracts", Window(start=date(2024, 1, 1), end=date(2024, 1, 31)), tmp_path
        )
    assert lake_calls == []


def test_snapshot_with_backfill_takes_a_window_or_none(cne: LakeConfigurer, tmp_path: Path) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    window = Window(start=date(2024, 2, 1), end=date(2024, 2, 29))
    with_window = provider.export("index_constituents", window, tmp_path / "a")
    assert with_window.window is not None and with_window.window.end == date(2024, 2, 29)
    whole = provider.export("index_constituents", None, tmp_path / "b")
    assert whole.window is None
    verify_revision(tmp_path / "a", with_window)
    verify_revision(tmp_path / "b", whole)


def test_truncated_calendar_is_refused(cne: LakeConfigurer, tmp_path: Path) -> None:
    lake = default_lake()
    lake["calendar"]["last"] = "2024-03-15"
    provider = CnequityProvider(cne_bin=cne(lake))
    with pytest.raises(ValueError, match=r"calendar.*2024-03-15"):
        provider.export(
            "option_bars", Window(start=date(2024, 2, 1), end=date(2024, 3, 31)), tmp_path
        )


def test_calendar_hole_is_refused(cne: LakeConfigurer, tmp_path: Path) -> None:
    lake = default_lake()
    lake["calendar"]["holes"] = ["2024-02-05"]
    provider = CnequityProvider(cne_bin=cne(lake))
    with pytest.raises(ValueError, match=r"calendar.*2024-02-05"):
        provider.export(
            "option_bars", Window(start=date(2024, 2, 1), end=date(2024, 2, 29)), tmp_path
        )


def test_end_beyond_the_last_date_is_refused_naming_first_missing_and_last(
    cne: LakeConfigurer, tmp_path: Path
) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    with pytest.raises(ValueError, match=r"2026-11-27.*2026-11-26"):
        provider.export(
            "option_bars", Window(start=date(2026, 11, 1), end=date(2026, 12, 31)), tmp_path
        )


def test_after_close_update_makes_the_day_present(cne: LakeConfigurer, tmp_path: Path) -> None:
    lake = default_lake()
    lake["datasets"]["option_bars"]["dates"].append("2026-11-27")
    provider = CnequityProvider(cne_bin=cne(lake))
    record = provider.export(
        "option_bars", Window(start=date(2026, 11, 1), end=date(2026, 11, 27)), tmp_path
    )
    assert record.window is not None and record.window.end == date(2026, 11, 27)


def test_window_ending_on_a_weekend_passes(cne: LakeConfigurer, tmp_path: Path) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    record = provider.export(
        "option_bars", Window(start=date(2024, 3, 1), end=date(2024, 3, 31)), tmp_path
    )
    assert record.window is not None and record.window.end == date(2024, 3, 31)


def test_mid_window_gap_is_refused(cne: LakeConfigurer, tmp_path: Path) -> None:
    lake = default_lake()
    lake["datasets"]["option_bars"]["dates"].remove("2024-02-05")
    provider = CnequityProvider(cne_bin=cne(lake))
    with pytest.raises(ValueError, match=r"option_bars.*2024-02-05"):
        provider.export(
            "option_bars", Window(start=date(2024, 2, 1), end=date(2024, 2, 29)), tmp_path
        )


def test_snapshot_export_passes_no_window_to_the_lake(
    cne: LakeConfigurer, lake_calls: list[list[str]], tmp_path: Path
) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    record = provider.export("option_contracts", None, tmp_path)
    assert record.window is None
    assert all("--start" not in call and "--end" not in call for call in lake_calls)
    verify_revision(tmp_path, record)


def test_two_windows_share_the_lake_id_but_not_the_pin(cne: LakeConfigurer, tmp_path: Path) -> None:
    provider = CnequityProvider(cne_bin=cne(default_lake()))
    first = provider.export(
        "option_bars", Window(start=date(2024, 1, 2), end=date(2024, 1, 5)), tmp_path / "a"
    )
    second = provider.export(
        "option_bars", Window(start=date(2024, 2, 1), end=date(2024, 2, 5)), tmp_path / "b"
    )
    assert (
        first.revision_id
        == second.revision_id
        == "option_bars@lake:dd97f8582206451f831c53f4cc6afce2"
    )
    assert first.window != second.window and first.content_digest != second.content_digest
    verify_revision(tmp_path / "a", first)
    verify_revision(tmp_path / "b", second)
