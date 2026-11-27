"""Immutable provider reports, distinct from committed order lifecycle facts."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VenueSide = Literal["BUY", "SELL"]
VenueOffset = Literal["OPEN", "CLOSE", "CLOSE_TODAY", "CLOSE_YESTERDAY"]
RecoveryDirection = Literal["LONG", "SHORT"]


class VenueOrderKind(StrEnum):
    """Provider observations; none independently authorize a canonical transition."""

    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class VenueOrderObservation(BaseModel):
    """Preserve provider status and correlation without inventing absent evidence.

    Quantities are reported observations, not instructions to create missing fills.
    Missing account/time/sequence must be resolved by the runtime before application.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: VenueOrderKind
    request_id: str | None = Field(default=None, min_length=1)
    order_ref: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: VenueSide | None = None
    offset: VenueOffset | None = None
    raw_status: str = Field(min_length=1)
    original_quantity: float | None = Field(default=None, gt=0)
    cumulative_quantity: float = Field(ge=0)
    remaining_quantity: float = Field(ge=0)
    venue_order_id: str | None = None
    provider_name: str | None = None
    account_id: str | None = None
    front_id: int | None = None
    session_id: int | None = None
    reason: str | None = None
    observed_at: datetime | None = None
    sequence: int | None = Field(default=None, ge=0)


class VenueExecutionObservation(BaseModel):
    """One execution reported by a provider, with no canonical-state defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    source_execution_id: str = Field(min_length=1)
    order_ref: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: VenueSide
    offset: VenueOffset
    price: float = Field(gt=0)
    quantity: float = Field(gt=0)
    remaining_quantity: float | None = Field(default=None, ge=0)
    cumulative_quantity: float | None = Field(default=None, ge=0)
    venue_order_id: str | None = None
    occurred_at: datetime | None = None
    trading_date: date | None = None
    sequence: int | None = Field(default=None, ge=0)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class VenueReportKind(StrEnum):
    """Kinds accepted by the serialized gateway report ingress."""

    ORDER = "ORDER"
    EXECUTION = "EXECUTION"
    UNRESOLVED = "UNRESOLVED"


class VenueReport(BaseModel):
    """Provider-scoped envelope drained by a runtime-owned serialized ingress.

    Optional identity fields are explicit missing evidence. Consumers must quarantine
    incomplete reports rather than infer account, command, order, time, or sequence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    kind: VenueReportKind
    provider_name: str = Field(min_length=1)
    account_id: str | None = None
    command_id: str | None = None
    order_id: str | None = None
    order: VenueOrderObservation | None = None
    execution: VenueExecutionObservation | None = None
    unresolved_reason: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "VenueReport":
        """Require exactly the payload represented by ``kind``."""
        if self.kind is VenueReportKind.ORDER and self.order is None:
            raise ValueError("ORDER report requires an order observation")
        if self.kind is VenueReportKind.EXECUTION and self.execution is None:
            raise ValueError("EXECUTION report requires an execution observation")
        if self.kind is VenueReportKind.UNRESOLVED and not self.unresolved_reason:
            raise ValueError("UNRESOLVED report requires a reason")
        if self.kind is not VenueReportKind.ORDER and self.order is not None:
            raise ValueError("order payload is only valid for ORDER reports")
        if self.kind is not VenueReportKind.EXECUTION and self.execution is not None:
            raise ValueError("execution payload is only valid for EXECUTION reports")
        return self


class RecoveryReadiness(StrEnum):
    """Runtime-owned venue recovery barrier state."""

    READY = "READY"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"


class RecoveryScope(BaseModel):
    """Provider/account/session scope whose dispatch readiness is independent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_name: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class RecoveryApplicationEvidence(BaseModel):
    """Shared-application evidence required before dispatch resumes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_name: str
    account_id: str
    cumulative_by_order: dict[str, float] = Field(default_factory=dict)
    source_command_ids: tuple[str, ...] = ()
    unresolved_report_ids: tuple[str, ...] = ()
    incomplete_stage_ids: tuple[str, ...] = ()
    account: "RecoveryAccountSnapshot"
    positions: tuple["RecoveryPositionSnapshot", ...] = ()


class RecoveryPositionSnapshot(BaseModel):
    """Comparable provider/shared-core position evidence at one recovery cut."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    symbol: str = Field(min_length=1)
    direction: RecoveryDirection
    quantity: float = Field(ge=0)
    avg_price: float = Field(ge=0)
    margin: float = Field(ge=0)


class RecoveryAccountSnapshot(BaseModel):
    """Comparable provider/shared-ledger account evidence at one recovery cut."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    cash: float
    equity: float
    available: float
    margin: float = Field(ge=0)
    commission: float = Field(ge=0)
    realized_pnl: float
    unrealized_pnl: float


class RecoveryQueryStatus(StrEnum):
    """Outcome of an authoritative provider recovery query."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNSUPPORTED = "UNSUPPORTED"


class RecoveryCommandState(StrEnum):
    """Authoritative disposition of one original client command."""

    SUBMITTED = "SUBMITTED"
    NOT_SUBMITTED = "NOT_SUBMITTED"
    UNKNOWN = "UNKNOWN"


class RecoveryQueryResult(BaseModel):
    """Typed recovery result; local caches cannot represent completeness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: RecoveryQueryStatus
    capability: str = Field(min_length=1)
    reason: str | None = None
    reports: tuple[VenueReport, ...] = ()
    checkpoint: str | None = None
    provider_name: str | None = None
    account_id: str | None = None
    session_id: str | None = None
    query_cut: datetime | None = None
    pagination_exhausted: bool = False
    callback_merge_complete: bool = False
    command_id: str | None = None
    command_state: RecoveryCommandState | None = None
    dispatch_coverage_start: datetime | None = None
    dispatch_coverage_end: datetime | None = None
    history_coverage_start: datetime | None = None
    history_coverage_end: datetime | None = None
    provider_account: RecoveryAccountSnapshot | None = None
    provider_positions: tuple[RecoveryPositionSnapshot, ...] = ()

    @classmethod
    def unsupported(cls, capability: str) -> "RecoveryQueryResult":
        """Return an explicit unsupported capability result."""
        return cls(
            status=RecoveryQueryStatus.UNSUPPORTED,
            capability=capability,
            reason=f"provider does not support {capability}",
        )
