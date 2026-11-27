"""A fake `cne` for tests: the lake's CLI surface (`--version`, `storage export`) writing real
tiny Parquet, with the lake's behaviour for windows. The lake is described by a JSON document in
the `FAKE_CNE_LAKE` environment variable:

    {"revision_id": "...", "calendar": {"first": "2023-11-26", "last": "2027-11-26",
                                        "holes": [], "holidays": []},
     "datasets": {"option_bars": {"mode": "by_date", "dates": ["2024-01-02", ...]},
                  "option_contracts": {"mode": "snapshot_only", "rows": 3}}}

`trading_calendar` is generated from `calendar`; dated datasets hold their `trade_date` values;
snapshot datasets hold `rows` synthetic rows. The revision id is per dataset version, never per
window — as the real lake reports it.
"""

from __future__ import annotations

import sys
import textwrap
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_SCRIPT = textwrap.dedent(
    """
    import json
    import os
    import sys
    from datetime import date, timedelta
    from pathlib import Path

    import pyarrow as pa
    import pyarrow.parquet as pq

    lake = json.loads(os.environ["FAKE_CNE_LAKE"])
    args = sys.argv[1:]
    if args[:1] == ["--version"]:
        print("cne, version 0.25.0")
        sys.exit(0)
    if args[:2] != ["storage", "export"]:
        print(f"Usage: cne storage export --out DIR [--start D --end D] DATASET...", file=sys.stderr)
        sys.exit(2)
    out = None
    start = end = None
    datasets = []
    it = iter(args[2:])
    for arg in it:
        if arg == "--out":
            out = Path(next(it))
        elif arg == "--start":
            start = date.fromisoformat(next(it))
        elif arg == "--end":
            end = date.fromisoformat(next(it))
        else:
            datasets.append(arg)

    def calendar_days():
        cal = lake["calendar"]
        holes = {date.fromisoformat(d) for d in cal.get("holes", [])}
        holidays = {date.fromisoformat(d) for d in cal.get("holidays", [])}
        d = date.fromisoformat(cal["first"])
        last = date.fromisoformat(cal["last"])
        while d <= last:
            if d not in holes:
                yield d, d.weekday() < 5 and d not in holidays
            d += timedelta(days=1)

    def rows_of(name):
        spec = lake["datasets"][name]
        if name == "trading_calendar":
            days = [(d, t) for d, t in calendar_days() if (start is None or d >= start) and (end is None or d <= end)]
            return [(d, t) for d, t in days]
        if spec["mode"] == "snapshot_only":
            anchor = date.fromisoformat(lake["calendar"]["last"])
            return [(anchor, None)] * spec.get("rows", 1)
        days = [date.fromisoformat(d) for d in spec["dates"]]
        return [(d, None) for d in days if (start is None or d >= start) and (end is None or d <= end)]

    exported = []
    for name in datasets:
        spec = lake["datasets"][name]
        if spec["mode"] == "snapshot_only" and (start is not None or end is not None):
            print(f"Error: {name} has no date column to select a range by", file=sys.stderr)
            sys.exit(1)
        rows = rows_of(name)
        target = out / name
        target.mkdir(parents=True, exist_ok=True)
        files = 0
        size = 0
        by_month = {}
        for trade_date, is_trading in rows:
            by_month.setdefault((trade_date.year, trade_date.month), []).append((trade_date, is_trading))
        for (year, month), group in sorted(by_month.items()):
            part = target / f"year={year}" / f"month={month}"
            part.mkdir(parents=True, exist_ok=True)
            columns = {"trade_date": pa.array([g[0] for g in group], pa.date32())}
            if name == "trading_calendar":
                columns["is_trading"] = pa.array([bool(g[1]) for g in group], pa.bool_())
            else:
                columns["symbol"] = pa.array(["X"] * len(group), pa.string())
            table = pa.table(columns)
            path = part / "data_0.parquet"
            pq.write_table(table, path)
            files += 1
            size += path.stat().st_size
        exported.append({"dataset": name, "rows": len(rows), "files": files, "bytes": size,
                         "revision_id": lake["revision_id"], "snapshot": 73, "path": str(target)})
    print(json.dumps({"exported": exported}))
    """
)


def install_fake_cne(tmp_path: Path) -> str:
    """Write the fake `cne` next to the test's interpreter and return its path."""
    script = tmp_path / "cne"
    script.write_text(f"#!{sys.executable}\n{_SCRIPT}", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


COVERAGE_START = date(2023, 11, 26)
HOLIDAYS = {date(2024, 1, 1)}


def trading_days(start: date, end: date) -> list[date]:
    """Weekdays that are not holidays — the fake lake's calendar rule."""
    days = []
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in HOLIDAYS:
            days.append(day)
        day += timedelta(days=1)
    return days


def default_lake() -> dict[str, Any]:
    """A lake whose option data covers every trading day from the coverage start to 2026-11-26,
    with a calendar running to 2027; tests mutate it to plant gaps."""
    days = [d.isoformat() for d in trading_days(COVERAGE_START, date(2026, 11, 26))]
    return {
        "revision_id": "dd97f8582206451f831c53f4cc6afce2",
        "calendar": {
            "first": COVERAGE_START.isoformat(),
            "last": "2027-11-26",
            "holes": [],
            "holidays": [d.isoformat() for d in HOLIDAYS],
        },
        "datasets": {
            "option_bars": {"mode": "by_date", "dates": days},
            "option_greeks": {"mode": "by_date", "dates": days},
            "option_contracts": {"mode": "snapshot_only", "rows": 3},
            "futures_contracts": {"mode": "snapshot_only", "rows": 2},
            "instruments": {"mode": "snapshot_only", "rows": 5},
            "index_constituents": {
                "mode": "snapshot_with_backfill",
                "dates": ["2024-01-31", "2024-02-29", "2024-03-29"],
            },
            "trading_calendar": {"mode": "by_date"},
        },
    }


LakeConfigurer = Callable[[dict[str, Any]], str]
