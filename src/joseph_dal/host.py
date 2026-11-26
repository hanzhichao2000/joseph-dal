"""Host: entry-point discovery and strict-local admission. Protocols only; no provider behavior."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

from joseph_api import RevisionRecord

from joseph_dal.exceptions import LiveTransportRefused, ProviderDiscoveryError
from joseph_dal.protocols import PROVIDER_ENTRY_POINT_GROUP, DataProvider, ReadPolicy


def discover_providers(group: str = PROVIDER_ENTRY_POINT_GROUP) -> dict[str, DataProvider]:
    """Load every provider registered under the entry-point group, keyed by entry-point name."""
    providers: dict[str, DataProvider] = {}
    try:
        eps = entry_points(group=group)
    except TypeError as exc:  # pragma: no cover - platform metadata differences
        raise ProviderDiscoveryError(f"cannot read entry-point group {group!r}: {exc}") from exc
    for ep in eps:
        try:
            obj = ep.load()
        except Exception as exc:  # noqa: BLE001 - report the entry point, not the traceback
            raise ProviderDiscoveryError(f"entry point {ep.name!r} failed to load: {exc}") from exc
        if isinstance(obj, type):
            obj = obj()
        if not isinstance(obj, DataProvider):
            raise ProviderDiscoveryError(f"entry point {ep.name!r} does not implement DataProvider")
        providers[ep.name] = obj
    return providers


def admit(provider: DataProvider, read_policy: ReadPolicy) -> None:
    """Strict-local admits only file-backed providers; nothing live is ever constructed."""
    if read_policy == "strict_local" and "live" in provider.transports:
        raise LiveTransportRefused(provider.provider_id)


def locate(record: RevisionRecord, root: Path) -> Path:
    """Default locator: the record's files are relative to ``root``; the first file must exist."""
    if not record.files:
        raise FileNotFoundError(f"revision {record.revision_id!r} lists no files")
    return root / record.files[0].path


__all__ = ["admit", "discover_providers", "locate"]
