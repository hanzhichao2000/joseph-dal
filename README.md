# joseph-dal

Data layer for the joseph-* family: a plugin host plus provider plugins. Every run reads pinned
revisions (capability, version, source, revision id, digest; receipt plus immutable relative-path
file list with per-file digests). Engines never call live sources during replay.

Providers ship as separate plugins (e.g. `dal-cnequity`).

For cnequity datasets with a declared coverage start, that date is the source data start, not
an assurance that the calendar verifies all subsequent data. When an export begins before the
trading calendar's actual start, the revision lists a digest-protected `<capability>.coverage.json`
file containing `calendar_unverified: {start, end}` for the inclusive prefix. This is a declarative
quality downgrade, not an exemption or a completeness claim: consumers must not treat that prefix
as calendar-verified or covered. Remaining dates require a calendar row for every calendar day and
an exported row for every trading day; missing dates or a window beyond the calendar end are refused.
A window entirely before the calendar start is wholly unverified. The declaration records the
calendar's known start, not a measurement of data completeness in the prefix.

The `industry_members` capability is a sparse industry-mapping snapshot: the lake currently has
only a single snapshot and no historical month-end coverage is promised. A window is optional and
does not imply completeness.

Boundaries:

- The host imports no provider plugin; providers are discovered by entry points.
- Provider declarations identify the sources available for point-in-time margin and commission data.
- Keep run manifests and generated reports out of this repository.
- Public contracts: https://github.com/hanzhichao2000/joseph-docs-public
