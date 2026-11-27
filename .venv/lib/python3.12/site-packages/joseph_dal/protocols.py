"""Provider protocol (see joseph-docs-public/contracts/provider-protocol.md).

The host imports no provider module by name and contains no provider literal.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from joseph_api import RevisionRecord
from pydantic import BaseModel, ConfigDict

ReadPolicy = Literal["live", "strict_local", "local_first"]
Transport = Literal["live", "file"]
ReplayPolicy = Literal["never_replay_dispatched", "idempotent_refetch"]
OnGap = Literal["dispatch", "reject"]

PROVIDER_ENTRY_POINT_GROUP = "joseph_dal.providers"


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: date
    end: date


class CapabilityDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_id: str
    schema_version: str
    source: str
    history_mode: Literal["by_date", "snapshot_with_backfill", "snapshot_only"]
    window_limits: Window | None = None
    coverage_start: date | None = None
    derived_from: tuple[str, ...] | None = None


@runtime_checkable
class DataProvider(Protocol):
    """What a provider plugin exposes through the entry-point group."""

    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> tuple[CapabilityDeclaration, ...]: ...

    @property
    def replay_policy(self) -> ReplayPolicy: ...

    @property
    def transports(self) -> tuple[Transport, ...]: ...

    def export(self, capability: str, window: Window | None, out_dir: Path) -> RevisionRecord: ...

    def locate(self, record: RevisionRecord, root: Path) -> Path: ...


@runtime_checkable
class Preflight(Protocol):
    """Admission contract; its implementation is adopted from the core host when it lands."""

    def admit(self, provider: DataProvider, read_policy: ReadPolicy) -> None: ...


@runtime_checkable
class RevisionLocator(Protocol):
    def locate(self, record: RevisionRecord, root: Path) -> Path: ...
