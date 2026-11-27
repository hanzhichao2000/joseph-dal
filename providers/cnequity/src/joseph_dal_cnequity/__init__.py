"""cnequity provider: shells out to the lake CLI (never imports cnequity) and returns a revision.

Every dataset is declared with the history mode its export path really supports, a coverage
start where the lake's calendar can verify it, and the datasets it is derived from. For a dataset
with a coverage start, a windowed export is fail-closed: refused before any lake call when it
starts before the coverage start, and refused after export when the calendar does not cover the
window or any trading day in it is absent from the written files. Sparse datasets (month-end
snapshots) carry no coverage start and make no coverage claim.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import pyarrow.parquet as pq
from joseph_api import RevisionFile, RevisionRecord, RevisionWindow

from joseph_dal.protocols import CapabilityDeclaration, ReplayPolicy, Transport, Window

HistoryMode = Literal["by_date", "snapshot_with_backfill", "snapshot_only"]
_CALENDAR = "trading_calendar"
_DATE_COLUMN = "trade_date"


@dataclass(frozen=True)
class DatasetSpec:
    """What the export path really does for one dataset, and where its coverage can be verified."""

    mode: HistoryMode
    coverage_start: date | None = None
    derived_from: tuple[str, ...] | None = None


# dataset -> (history mode, coverage start, derived from). `coverage_start` is the lake calendar's
# first date where it applies: every trading day of an accepted window can then be checked.
_DATASETS: dict[str, DatasetSpec] = {
    "instruments": DatasetSpec("snapshot_only"),
    "index_constituents": DatasetSpec("snapshot_with_backfill"),
    "index_bars": DatasetSpec("by_date"),
    "daily_bars": DatasetSpec("by_date"),
    "futures_bars": DatasetSpec("by_date"),
    "futures_contracts": DatasetSpec("snapshot_only"),
    "option_contracts": DatasetSpec("snapshot_only"),
    "option_bars": DatasetSpec("by_date", coverage_start=date(2023, 11, 26)),
    "option_greeks": DatasetSpec(
        "by_date",
        coverage_start=date(2023, 11, 26),
        derived_from=("option_bars", "option_contracts"),
    ),
    _CALENDAR: DatasetSpec("by_date", coverage_start=date(2023, 11, 26)),
}
_SCHEMA_VERSION = "cne-contract-0.25.0"


class CoverageError(ValueError):
    """A window the source cannot vouch for: before the coverage start, outside its calendar, or
    with a trading day missing from the written files. Nothing partial is returned."""


class CnequityProvider:
    provider_id = "cnequity"
    transports: tuple[Transport, ...] = ("live", "file")
    replay_policy: ReplayPolicy = "idempotent_refetch"

    def __init__(self, cne_bin: str = "cne", source_version: str | None = None) -> None:
        self._cne_bin = cne_bin
        self._source_version = source_version

    def _version(self) -> str:
        if self._source_version is None:
            out = subprocess.run(
                [self._cne_bin, "--version"], capture_output=True, text=True, check=True
            )
            self._source_version = out.stdout.strip().split()[-1]
        return self._source_version

    @property
    def capabilities(self) -> tuple[CapabilityDeclaration, ...]:
        source = f"cnequity@{self._version()}"
        return tuple(
            CapabilityDeclaration(
                capability_id=name,
                schema_version=_SCHEMA_VERSION,
                source=source,
                history_mode=spec.mode,
                coverage_start=spec.coverage_start,
                derived_from=spec.derived_from,
            )
            for name, spec in _DATASETS.items()
        )

    def _check_window(self, capability: str, spec: DatasetSpec, window: Window | None) -> None:
        """Refuse what the export path cannot honour, before any lake call."""
        if spec.mode == "by_date" and window is None:
            raise ValueError(f"{capability!r} is dated; a window is required")
        if spec.mode == "snapshot_only" and window is not None:
            raise ValueError(f"{capability!r} exports only as a whole; a window is not accepted")
        if window is not None:
            if window.end < window.start:
                raise ValueError(f"{capability!r}: window end {window.end} precedes its start")
            if spec.coverage_start is not None and window.start < spec.coverage_start:
                raise CoverageError(
                    f"{capability!r}: window start {window.start} precedes the coverage start "
                    f"{spec.coverage_start}; request from {spec.coverage_start} on"
                )

    def _export_raw(
        self, out_dir: Path, window: Window | None, datasets: list[str]
    ) -> dict[str, Any]:
        """Run `cne storage export` and return the receipt JSON it prints on stdout."""
        cmd = [self._cne_bin, "storage", "export", "--out", str(out_dir)]
        if window is not None:
            cmd += ["--start", window.start.isoformat(), "--end", window.end.isoformat()]
        cmd += datasets
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return cast(dict[str, Any], json.loads(proc.stdout[proc.stdout.index("{") :]))

    def export(self, capability: str, window: Window | None, out_dir: Path) -> RevisionRecord:
        spec = _DATASETS.get(capability)
        if spec is None:
            raise ValueError(f"unknown cnequity dataset {capability!r}")
        self._check_window(capability, spec, window)
        out_dir.mkdir(parents=True, exist_ok=True)
        report = self._export_raw(out_dir, window, [capability])
        exported = next(e for e in report["exported"] if e["dataset"] == capability)
        dataset_dir = out_dir / capability
        files = tuple(
            RevisionFile(
                path=p.relative_to(out_dir).as_posix(),
                digest=hashlib.sha256(p.read_bytes()).hexdigest(),
                size=p.stat().st_size,
            )
            for p in sorted(dataset_dir.rglob("*"))
            if p.is_file()
        )
        if not files:
            raise RuntimeError(f"cne storage export wrote no files for {capability!r}")
        source = f"cnequity@{self._version()}"
        digest = RevisionRecord.compute_content_digest(capability, _SCHEMA_VERSION, source, files)
        record = RevisionRecord(
            capability_id=capability,
            schema_version=_SCHEMA_VERSION,
            source=source,
            revision_id=f"{capability}@lake:{exported['revision_id']}",
            content_digest=digest,
            files=files,
            window=RevisionWindow(start=window.start, end=window.end) if window else None,
        )
        if window is not None and spec.coverage_start is not None:
            self._check_coverage(capability, window, record, out_dir)
        (out_dir / f"{capability}.revision.json").write_text(record.to_json(), encoding="utf-8")
        return record

    def _check_coverage(
        self, capability: str, window: Window, record: RevisionRecord, out_dir: Path
    ) -> None:
        """Fail closed unless the calendar vouches for the window and every trading day in it is
        in the written files. Footer min/max is a cheap bounds pre-check; the distinct dates are
        always read from the date column, because min/max cannot show a day missing in the middle."""
        with self._temporary_calendar(window) as calendar_dir:
            calendar = _read_calendar(calendar_dir)
        calendar_days = set(calendar)
        uncovered = sorted(_dates_between(window.start, window.end) - calendar_days)
        if uncovered:
            last = max(calendar_days) if calendar_days else None
            raise CoverageError(
                f"{capability}: the source calendar does not cover the window: first missing day "
                f"{uncovered[0]}, calendar last date {last}"
            )
        trading_days = {
            day for day in calendar if calendar[day] and window.start <= day <= window.end
        }
        present: set[date] = set()
        for entry in record.files:
            path = out_dir / entry.path
            _bounds_precheck(capability, entry.path, path, window)
            present |= set(pq.read_table(path, columns=[_DATE_COLUMN]).column(0).to_pylist())
        missing = sorted(trading_days - present)
        if missing:
            last = max(present) if present else None
            raise CoverageError(
                f"{capability}: the export does not cover the window: first missing trading day "
                f"{missing[0]}, last date in the files {last}"
            )

    @contextmanager
    def _temporary_calendar(self, window: Window) -> Iterator[Path]:
        """The lake's trading calendar for the window, exported to a directory that does not outlive
        the check."""
        with tempfile.TemporaryDirectory() as tmp:
            self._export_raw(Path(tmp), window, [_CALENDAR])
            yield Path(tmp) / _CALENDAR

    def locate(self, record: RevisionRecord, root: Path) -> Path:
        return root / record.files[0].path


def _dates_between(start: date, end: date) -> set[date]:
    days: set[date] = set()
    day = start
    while day <= end:
        days.add(day)
        day += timedelta(days=1)
    return days


def _bounds_precheck(capability: str, name: str, path: Path, window: Window) -> None:
    """Cheap check from the Parquet footer: the file's date range must touch the window."""
    parquet = pq.ParquetFile(path)
    column = parquet.schema_arrow.names.index(_DATE_COLUMN)
    lows: list[date] = []
    highs: list[date] = []
    for group in range(parquet.metadata.num_row_groups):
        stats = parquet.metadata.row_group(group).column(column).statistics
        if stats is not None and stats.min is not None and stats.max is not None:
            lows.append(stats.min)
            highs.append(stats.max)
    if lows and (max(highs) < window.start or min(lows) > window.end):
        raise CoverageError(
            f"{capability}: {name} holds {_DATE_COLUMN} {min(lows)}..{max(highs)}, outside the window"
        )


def _read_calendar(parquet_dir: Path) -> dict[date, bool]:
    """`trade_date -> is_trading` from every Parquet file of an exported calendar."""
    flags: dict[date, bool] = {}
    for path in sorted(parquet_dir.rglob("*.parquet")):
        table = pq.read_table(path, columns=[_DATE_COLUMN, "is_trading"])
        days = table.column(0).to_pylist()
        flags.update(zip(days, table.column(1).to_pylist(), strict=True))
    return flags


def load_receipt(path: Path) -> RevisionRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RevisionRecord.model_validate(data)


__all__ = ["CnequityProvider", "CoverageError", "DatasetSpec", "load_receipt"]
