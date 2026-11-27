# joseph-dal

Data layer for the joseph-* family: a plugin host plus provider plugins. Every run reads pinned
revisions (capability, version, source, revision id, digest; receipt plus immutable relative-path
file list with per-file digests). Engines never call live sources during replay.

Routes (Project `joseph-build` #6):

- **B (options):** `option_contracts` / `option_bars` / `option_greeks` interface design on
  cnequity (CFE official daily since 2019-12-23). Options strategy notebooks are ad-hoc and live
  outside this repository.
- **C (IH daily research):** daily bars, constituents, industry and calendar for joseph-pilot.
- **A (QT5m):** 5-minute futures bars by contract (akshare/Sina) and CFE daily/contracts
  (cnequity).

For cnequity datasets with a declared coverage start, that date is the source data start, not
an assurance that the calendar verifies all subsequent data. When an export begins before the
trading calendar's actual start, the revision lists a digest-protected `<capability>.coverage.json`
file containing `calendar_unverified: {start, end}` for the inclusive prefix. This is a declarative
quality downgrade, not an exemption or a completeness claim: consumers must not treat that prefix
as calendar-verified or covered. Remaining dates require a calendar row for every calendar day and
an exported row for every trading day; missing dates or a window beyond the calendar end are refused.
A window entirely before the calendar start is wholly unverified. The declaration records the
calendar's known start, not a measurement of data completeness in the prefix.

Boundaries:

- The host imports no provider plugin; providers are discovered by entry points.
- `dal-tsl` is private (vendor). Margin and commission PIT has no open-source substitute: it is
  declared, never claimed open.
- New evidence attaches to GitHub Issues as run manifests; no report trees in this repository.
- Public contracts: https://github.com/hanzhichao2000/joseph-docs-public
